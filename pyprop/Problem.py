import signal
from pyproplogging import GetClassLogger, GetFunctionLogger

RedirectInterrupt = False

def CreateWavefunction(config):
	"""
	Creates a Wavefunction from a config file. Use this function if
	you only need a wavefunction and not a complete proapagator.

	The wavefunction will have one data buffer allocated, and the content
	is unspecified.

	ex:
	conf = pyprop.Load("config.ini")
	psi = CreateWavefunction(config)
	x = psi.GetData().GetRepresentation().GetLocalGrid(0)
	psi.GetData()[:] = x * exp(- x**2)
	"""
	logger = GetFunctionLogger()

	logger.debug("Creating DistributionModel...")
	distribution = CreateDistribution(config)

	logger.debug("Creating Representation...")
	representation = CreateRepresentation(config, distribution)

	logger.debug("Creating Wavefunction...")
	psi = CreateWavefunctionInstance(representation)

	return psi


def LoadConfigFromFile(filename, datasetPath="/wavefunction"):
	f = tables.openFile(filename, "r")
	try:
		dataset = serialization.GetExistingDataset(f, datasetPath)
		conf = Config(dataset._v_attrs.configObject)

	finally:
		f.close()

	return conf
	

def CreateWavefunctionFromFile(filename, datasetPath="/wavefunction"):
	"""
	Loads a wavefunction directly from a HDF5-file. The config object
	is read from the attribute configObject on the node specified by
	datasetPath
	"""
	conf = LoadConfigFromFile(filename, datasetPath)
	psi = CreateWavefunction(conf)
	serialization.LoadWavefunctionHDF(filename, datasetPath, psi)

	return psi


#----------------------------------------------------------------------------------------------------
# Problem
#----------------------------------------------------------------------------------------------------
class Problem:
	"""
	This is the main class of pyprop. It reads a config object and sets up everything
	to allow propagation. See the examples folder for examples how to use this class.
	"""

	def __init__(self, config):
		self.TempPsi = None
		self.Config = config
		self.Logger = GetClassLogger(self)
		try:
			#Enable redirect
			if hasattr(config.Propagation, "silent"):
				self.Silent = config.Propagation.silent
			else:
				self.Silent = False
			redirectStateOld = Redirect.redirect_stdout
			Redirect.Enable(self.Silent)
		
			#Create wavefunction
			self.psi = CreateWavefunction(config)
		
			self.Logger.debug("Creating Propagator...")
			self.Propagator = CreatePropagator(config, self.psi)
		
			#apply propagation config
			config.Propagation.Apply(self)

			#Disable redirect
			if not redirectStateOld == Redirect.redirect_stdout:
				Redirect.Disable()

		except:
			#Diasable redirect
			Redirect.Disable()
			raise
			

	def GetGrid(self):
		"""
		Helper function to construct the grid in each rank of the wavefunction

		This method is most useful for cartesian coordinates, and possibly other
		non-compressed grids. For compressed grids (like spherical) the grid returned
		here will typically just be the idices converted to double
		"""
		#set up grid
		repr = self.psi.GetRepresentation()
		grid = [repr.GetLocalGrid(i) for i in range(0, self.psi.GetRank())]
		return grid
		
		
	#Propagation-------------------------------------------------
	def SetupStep(self, skipWavefunctionSetup=False):
		"""
		Runs the nescescary setup routines to allow propagation.

		This function must be called before the first call to AdvanceStep()
		or Advance().
		"""
		try:
			#Enable redirect
			redirectStateOld = Redirect.redirect_stdout
			Redirect.Enable(self.Silent)
			
			self.Logger.debug("Starting setup timestep...")
			self.Logger.debug("    Setting up Propagator.")
			if self.Propagator != None:
				self.Propagator.SetupStep(self.TimeStep)

			self.Logger.debug("    Setting up initial wavefunction")
			if not skipWavefunctionSetup:
				self.SetupWavefunction()
			
			self.Logger.info("Setup timestep complete.")
	
			#Disable redirect
			if not redirectStateOld:
				Redirect.Disable()

		except:
			#Diasable redirect
			Redirect.Disable()
			raise	

	def RestartPropagation(self, timestep, startTime, propagationTime):
		"""
		Resets propagation time, duration and timestep for all propagators,
		allowing the problem object to be propagated again without having
		to call SetupStep.
		"""
		self.TimeStep = timestep
		self.PropagatedTime = startTime
		self.StartTime = startTime
		self.Duration = propagationTime
		if self.Propagator != None:
				self.Propagator.RestartPropagation(timestep, startTime, propagationTime)


	def AdvanceStep(self):
		"""
		Advances the wavefunction one timestep.
	
		most of the work is done in the propagator object. This function
		is merley to keep a track of propagated time, and provide a simple 
		interface to the user.
		"""
		self.Propagator.AdvanceStep(self.PropagatedTime, self.TimeStep )
		if self.Propagator.RenormalizeActive:
			self.psi.Normalize()

		if abs(self.TimeStep.real) < 1e-10:
			self.PropagatedTime += abs(self.TimeStep)
		else:
			self.PropagatedTime += self.TimeStep.real


	def MultiplyHamiltonian(self, srcPsi, dstPsi):
		"""
		Applies the Hamiltonian to the wavefunction H psi -> psi
		"""
		self.Propagator.MultiplyHamiltonian(srcPsi, dstPsi, self.PropagatedTime, self.TimeStep )

	def Advance(self, yieldCount, duration=None, yieldEnd=False):
		"""
		Returns a generator for advancing the wavefunction a number of timesteps. 
		If duration is specified the wavefunction is propagated until propagated 
		time >= duration.

		if yieldCount is a number, it is the number of times this routine will 
		yield control back to the caller. 
		If is a boolean, yieldCount=True will make this function yield every timestep
		and yieldCount=False will make it yield one time. (at the last timestep (i think))

		if yieldEnd is True, a yield will be given at the end of propagation, regardless if 
		it matches the wanted number of yields
		"""
		if duration == None:
			duration = self.Duration

		#Determine how often we should yield.
		if yieldCount.__class__ is bool:
			yieldStep = 1
		else:
			yieldStep = int((duration / abs(self.TimeStep)) / yieldCount)

		#Modify the interrupt signal handler
		if RedirectInterrupt:
			try:
				InterruptHandler.UnRegister()
			except: pass
			InterruptHandler.Register()
	
		index = 0

		if self.TimeStep.real == 0:
			#negative imaginary time
			stoppingCriterion = lambda: (self.StartTime + self.Duration - self.PropagatedTime) > 0.5 * abs(self.TimeStep)
		else:
			endTime = self.StartTime + sign(self.TimeStep) * self.Duration
			#real time
			stoppingCriterion = lambda: abs(self.PropagatedTime - endTime) > 0.5 * abs(self.TimeStep)

		prevYield = numpy.NAN
		while stoppingCriterion():
			#next timestep
			self.AdvanceStep()

			#check keyboard interrupt
			if RedirectInterrupt:
				if InterruptHandler.IsInterrupted():
					InterruptHandler.ProcessInterrupt()
			
			index += 1
			if index % yieldStep == 0:
				yield self.PropagatedTime
				prevYield = self.PropagatedTime
		
		if yieldEnd and prevYield != self.PropagatedTime:
			yield self.PropagatedTime
	
		if RedirectInterrupt:
			InterruptHandler.UnRegister()

	def GetEnergy(self):
		if isreal(self.TimeStep):
			return self.GetEnergyExpectationValue()
		else:
			return self.GetEnergyImTime()

	def GetTempPsi(self):
		if self.TempPsi == None:
			self.TempPsi = self.psi.CopyDeep()
		return self.TempPsi

	def GetEnergyExpectationValue(self):
		"""
		Calculates the total energy of the problem by finding the expectation value 
		of the Hamiltonian
		"""
		self.psi.Normalize()

		#Make copy of wavefunction
		tempPsi = self.GetTempPsi()
		tempPsi.GetData()[:] = 0

		#Apply the Hamiltonian to the wavefunction
		self.MultiplyHamiltonian(self.psi, tempPsi)

		#Calculate the inner product between the applied psi and the original psi
		energy = self.psi.InnerProduct(tempPsi)

		#Check that the energy is real
		if not hasattr(self, "IgnoreWarningRealEnergy"):
			if abs(imag(energy)) > 1e-10:
				self.Logger.warning("Energy is not real (%s). Possible bug. Supressing further warnings of this type" % (energy))
				self.IgnoreWarningRealEnergy = True
		return energy.real
	
	def GetEnergyImTime(self):
		"""
		Advance one timestep without normalization and imaginary time.
		we can then find the energy by looking at the norm of the decaying
		wavefunction.

		This will only work when negative imaginary time is used to propagate
		to the groundstate, and will only give a good estimate for the ground
		state energy when the wavefunction is well converged to the ground state.

		Because it uses the norm of the wavefunction to measure energy, it will 
		be very sensitive to differences in the shape of the wavefunction.
		"""
		
		if isreal(self.TimeStep):
			raise "Can only find energy for imaginary time propagation"
		
		renorm = self.Propagator.RenormalizeActive
		self.psi.Normalize()
		self.Propagator.RenormalizeActive = False
		self.AdvanceStep()
		self.Propagator.RenormalizeActive = renorm
		
		norm = self.psi.GetNorm()
		self.psi.GetData()[:] /= norm
		energy = - log(norm**2) / (2 * abs(self.TimeStep))
		return energy
	
	#Initialization-----------------------------------------------
	def ApplyConfigSection(self, configSection):
			self.TimeStep = complex(configSection.timestep)
			self.Duration = configSection.duration
			self.PropagatedTime = 0
			self.StartTime = 0
			if hasattr(configSection, "start_time"):
				self.StartTime = configSection.start_time
				self.PropagatedTime = self.StartTime


	def SetupWavefunction(self):
		"""
		Initializes the wavefunction according to the initially specified configuration
		file.
		The supported initial condition types are:
		InitialConditionType.Function
			see SetupWavefunctionFunction()
			
		InitialConditionType.File
			See SetupWavefunctionFile()

		"""
		type = self.Config.InitialCondition.type
		if type == InitialConditionType.Function:
			self.SetupWavefunctionFunction(self.Config)
		elif type == InitialConditionType.File:
			self.SetupWavefunctionFile(self.Config)
		elif type == InitialConditionType.Class:
			self.SetupWavefunctionClass(self.Config, self.psi)
		elif type == InitialConditionType.Custom:
			self.SetupWavefunctionCustom(self.Config)
		elif type == None:
			pass
		else:
			raise "Invalid InitialConditionType: " + self.Config.InitialCondition.type
			
	def SetupWavefunctionClass(self, config, psi):
		classname = config.InitialCondition.classname
		
	  	#Create globals
		glob = dict(ProjectNamespace)
		glob.update(globals())	
	
		#try to
		evaluator = None
		try: evaluator = eval(classname + "()", glob)
		except: pass

		if evaluator == None:
			try: evaluator = eval(classname + "_" + str(psi.GetRank()) + "()", glob)
			except: pass

		if evaluator == None:
			raise "Invalid classname", classname

		config.Apply(evaluator)
		config.InitialCondition.Apply(evaluator)
		evaluator.SetupWavefunction(psi)

	def SetupWavefunctionFunction(self, config):
		"""
		Initializes the wavefunction from a function specified in the InitialCondition
		section of config. The function refrence config.InitialCondition.function 
		is evaulated in all grid points of the wavefunction, and the wavefunction is
		set up accordingly.

		for example. if this is a rank 2 problem, then this will initialize the wavefunction
		to a 2D gaussian wavepacket.
		
		def func(x,  conf):
			return exp(- x[0]**2 + x[1]**2])
		
		config.InitialCondition.function = func
		prop.SetupWavefunctionFunction(config)

		REMARK: This function should probably not be called on directly. Use SetupWavefunction()
		instead. That function will automatically determine the type of initial condition to be used.		
		"""
		func = config.InitialCondition.function
		conf = config.InitialCondition
		
		#TODO: We should get this class from Propagator in order to use a different
		#evaluator for a compressed (i.e. spherical) grid
		evalfunc = eval("core.SetWavefunctionFromGridFunction_" + str(self.psi.GetRank()))
		evalfunc(self.psi, func, conf)
	
	def SetupWavefunctionFile(self, config):
		"""
		Initializes the wavefunction from a file specified in the InitialCondition.filename
		according to the format InitialCondition.format. If InitialCondition.format is not 
		specified, this routine should automatically try to figure out which format it it, 
		but this is not yet implemented.

		See the functions LoadWavefunction*() SaveWavefunction*() for details on how to
		load and save wavefunctions

		REMARK: This function should probably not be called on directly. Use SetupWavefunction()
		instead. That function will automatically determine the type of initial condition to be used.		

		REMARK2: Currently it is not possible to interpolate a wavefunction between different grids. 
		this means that exactly the same grid used for saving the wavefunction must be used when loading
		it
		"""
		format   = config.InitialCondition.format
		filename = config.InitialCondition.filename
		
		if format == WavefunctionFileFormat.Ascii:
			self.LoadWavefunctionAscii(filename)
		elif format == WavefunctionFileFormat.Binary:
			self.LoadWavefunctionPickle(filename)
		elif format == WavefunctionFileFormat.HDF:
			datasetPath = str(config.InitialCondition.dataset)
			self.LoadWavefunctionHDF(filename, datasetPath)
		else:
			raise "Invalid file format: " + format
	
	def SetupWavefunctionCustom(self, config):
		"""
		Initializes the wavefunction from a function specified in the InitialCondition
		section of config. The function refrence config.InitialCondition.function 
		is evaulated called once, with the wavefunction as the first parameter, and
		the configSection as the second.

		REMARK: This function should probably not be called on directly. Use SetupWavefunction()
		instead. That function will automatically determine the type of initial condition to be used.		
		"""
		func = config.InitialCondition.function
		conf = config.InitialCondition
		func(self.psi, conf)

	#(de)serialization---------------------------------------------
	def LoadWavefunctionData(self, newdata):
		data = self.psi.GetData()
		if newdata.shape != data.shape:
			raise "Invalid shape on loaded wavefunction, got " + str(newdata.shape) + " expected " + str(data.shape)
		data[:] = newdata
		
	def SaveWavefunctionPickle(self, filename):
		serialization.SavePickleArray(filename, self.psi.GetData())
	
	def LoadWavefunctionPickle(self, filename):
		arr = serialization.LoadPickleArray(filename)
		self.LoadWavefunctionData(arr)

	def LoadWavefunctionHDF(self, filename, datasetPath):
		serialization.LoadWavefunctionHDF(filename, datasetPath, self.psi)

	def SaveWavefunctionHDF(self, filename, datasetPath):
		serialization.SaveWavefunctionHDF(filename, datasetPath, self.psi, conf=self.Config)

	def SaveWavefunctionAscii(self, filename):
		psiData = self.psi.GetData()
		assert(len(psiData.shape) <= 1)
		pylab.save(filename, transpose((psiData.real ,psiData.imag)), delimiter=' ')	

	def SaveWavefunctionFortran(self, filename):
		psiData = self.psi.GetData()
		assert(len(psiData.shape) <= 1)
		fh = open(filename, "w")
		for i in range(psiData.size):
			fh.write("(%s, %s) " % (psiData[i].real, psiData[i].imag) )
		fh.close()

	def LoadWavefunctionAscii(self, filename):
		r, c = pylab.load(filename, unpack=True)
		arr = r + 1.0j*c
		self.LoadWavefunctionData(arr)
		
	

