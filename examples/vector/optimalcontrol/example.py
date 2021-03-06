#import system modules
import sys
import os
from numpy import conj, size
from numpy import where as nwhere
import pylab
from numpy import fft

#pytables
import tables

#Pyprop itself
sys.path.append(os.environ["PYPROPPATH"])
import pyprop; 
pyprop = reload(pyprop)


def GetDiagonalElements(psi, config, potential):
	"""
	A funtion to provide diagonal (energy) matrix elements
	"""
	h5file = tables.openFile(config.filename, "r")
	try:
		potential[:] = h5file.getNode(config.dataset)[:config.size]
		potential[:] *= config.scaling	
	finally:
		h5file.close()


def Setup(**args):
	"""
	Setup optimal control problem
	"""
	print "Setting up control problem"

	configFile = 'config.ini'
	if "config" in args:
		configFile = args["config"]

	conf = pyprop.Load(configFile)

	if "dt" in args:
		dt = args["dt"]
		conf.SetValue("Propagation", "timestep", dt)

	controlAlgorithm = args.get("controlAlgorithm", "Krotov")
	print "    Using control algorithm: %s" % controlAlgorithm
	confSection = eval("conf.%s" % controlAlgorithm)

	if "bwdUpdate" in args:
		bwdUpdate = args["bwdUpdate"]
		conf.SetValue(controlAlgorithm, "update_backwards", bwdUpdate)
		print "Backward update: %s" % bwdUpdate

	maxIter = args.get("maxIter", confSection.max_iterations)
	conf.SetValue(controlAlgorithm, "max_iterations", maxIter)

	prop = pyprop.Problem(conf)
	prop.SetupStep()

	controlSolver = eval("pyprop.%s(prop)" % controlAlgorithm)
	controlSolver.ApplyConfigSection(confSection)
	controlSolver.Setup()

	return controlSolver


def Run():
	krotov = Setup()
	krotov.Run()

	return krotov


def GetPulseSpectrum(controlVector, timeGridResolution):
	dw = 2 * pi * fft.fftshift(fft.fftfreq(len(controlVector), timeGridResolution))
	pulseSpectrum = fft.fftshift(fft.fft(controlVector))
	return dw, pulseSpectrum


def ApplyFourierFilter(pulse, timeGridResolution, filterWidth = 1.0):
	"""
	Applies a low-pass filter to an optimized pulse. First, the fast 
	fourier transform of the pulse is computed, then a Gaussian filter
	centered at the zero frequency is applied. The width of the gaussian
	may be passed with the 'filterWidth' keyword.
	"""

	dw, pulseSpectrum = GetPulseSpectrum(pulse, timeGridResolution)
	pulseSpectrum *= exp(-dw**2 / filterWidth**2)
	filteredPulse = fft.ifft(fft.fftshift(pulseSpectrum)).real

	return filteredPulse


def MakeResultPlotCFY(solver = None, freqCutoff = 2.0, datasetPath = "/", controlNumber = 0):

	#Get results
	if solver == None:
		print "Please specify either oct object or HDF5 file."
		return
	elif solver.__class__ == str:
		h5file = tables.openFile(solver, "r")
		try:
			timeGrid = h5file.getNode(datasetPath, "TimeGrid")[:]
			timeGridResolution = timeGrid[1] - timeGrid[0]
			controlVector = h5file.getNode(datasetPath, "FinalControl")[controlNumber]
			octYield = h5file.getNode(datasetPath, "Yield")[:]
			pMethod = pyprop.PenaltyMethod.Projection
			forwardSolution = h5file.getNode(datasetPath, "ForwardSolution")[:]
			try:
				goodBadRatio = h5file.getNode(datasetPath, "GoodBadRatio")[:]
			except tables.NoSuchNodeError:
				pMethod = pyprop.PenaltyMethod.Energy
		finally:
			h5file.close()
	else:
		timeGrid = solver.TimeGrid
		timeGridResolution = solver.TimeGridResolution
		controlVector = solver.ControlVectors[controlNumber]
		octYield = solver.Yield
		pMethod = krotov.PenaltyMethod
		if pMethod == pyprop.PenaltyMethod.Projection:
			goodBadRatio = solver.GoodBadRatio[:]
	
	if pMethod == pyprop.PenaltyMethod.Projection:
		LaTeXFigureSettings(subFig=(2,3))
		figure()
		subplots = [subplot(321), subplot(322), subplot(323), subplot(324)]
		subplots += [axes([.125, .1, .78, .22])]
	else:
		LaTeXFigureSettings(subFig=(2,2))
		figure()
		subplots = [subplot(221), subplot(222), subplot(223), subplot(224)]

	#Plot final control
	subplots[0].plot(timeGrid, controlVector, label="Control function")
	subplots[0].set_xlabel("Time (a.u.)")
	subplots[0].legend(loc="best")

	#Plot control spectrum
	freq, controlSpectrum = GetPulseSpectrum(controlVector, timeGridResolution)
	spectrumSize = size(controlSpectrum)
	freq = freq[spectrumSize/2:]
	absSpectrum = abs(controlSpectrum[spectrumSize/2:])
	I = nwhere(freq > freqCutoff)[0][0]
	subplots[1].plot(freq[:I], absSpectrum[:I], label="Control spectrum")
	subplots[1].set_xlabel("Frequency (a.u.)")
	subplots[1].legend(loc="best")

	#Plot yield
	subplots[2].plot(octYield, label="Yield")
	subplots[2].axis([0, len(octYield), 0, 1.1])
	subplots[2].set_xlabel("Iteration number")
	subplots[2].legend(loc="best")

	#Plot bad/good ratio
	if pMethod == pyprop.PenaltyMethod.Projection:
		subplots[3].plot(r_[3:len(goodBadRatio)], goodBadRatio[3:], \
			label=r"$\sqrt{\frac{u^T\Phi_{bad}u}{u^T\Phi_{good}u}}$")
		subplots[3].set_xlabel("Iteration number")
		subplots[3].legend(loc="best")
	
	#Plot state populations
	ax = subplots[-1]
	ax.plot(timeGrid, abs(forwardSolution[0,:])**2, label=r"$|0\rangle$")
	ax.plot(timeGrid, abs(forwardSolution[1,:])**2, label=r"$|1\rangle$")
	ax.axis([timeGrid[0], timeGrid[-1], 0, 1.1])
	xlabel("Time (a.u.)")
	ylabel("Population")
	legend(loc="best")

	draw()
	
	return subplots

def TextToHDFDense(fileName, vectorSize, scaling):

	groupName = 'doubledot'
	datasetPath = '/' + groupName + '/matrixelements_50'
	data = pylab.load(fileName)

	fileh5 = tables.openFile(fileName + '.h5', 'w')
	
	try:
		group = fileh5.createGroup(fileh5.root, groupName)
		h5array = pyprop.serialization.CreateDataset(fileh5, datasetPath, (vectorSize,vectorSize))

		#Fill h5array with matrix element data
		for i in range(shape(data)[0]):
			row = int(data[i,0]) - 1
			col = int(data[i,1]) - 1
			matel = data[i,2] * scaling
			h5array[row, col] = matel 
			h5array[col,row] = matel

	finally:
		fileh5.close()


def ReadFortranComplexData(fileName, dataSize):
	"""
	Read complex data from an ASCII file, as stored by Fortran.
	Reads only the first line of the file.
	"""
	#Allocate data array
	data = numpy.zeros(dataSize, dtype=complex)

	#Open file
	fileHandle = open(fileName, 'r')

	#Read data line
	rawline = fileHandle.readline()
	line = rawline.split(') (')
	fileHandle.close()

	#Parse complex data
	for k in range(0, dataSize):
		line[k] = line[k].strip()
		line[k] = line[k].strip('(')
		line[k] = line[k].strip(')')
		line[k] = line[k].strip()
		num = line[k].split(',')
		num[0].strip()
		num[1].strip()
		data[k] = numpy.complex(float(num[0]),float(num[1]))

	return data


def SaveOptimalControlProblem(filename, datasetPath, solver):
	"""
	Stores the following results from an OCT run:
	    
	    -J (all iterations)
		-Yield (all iterations)
		-Time grid
		-Final control
		-Final wavefunction
		-Final forward solution
		-Final backward solution
		-Good/bad ratio
		-Control at max yield
		-Forward solution at max yield
	"""

	#Save wavefunction
	SaveWavefunction(filename, "%s/wavefunction" % datasetPath, solver.BaseProblem)

	#Store optimal control run results
	h5file = tables.openFile(filename, "r+")
	try:
		h5file.createArray(datasetPath, "J", solver.J)
		h5file.createArray(datasetPath, "Yield", solver.Yield)
		h5file.createArray(datasetPath, "FinalControl", solver.ControlVectors)
		h5file.createArray(datasetPath, "TimeGrid", solver.TimeGrid)
		h5file.createArray(datasetPath, "ForwardSolution", solver.ForwardSolution)
		h5file.createArray(datasetPath, "BackwardSolution", solver.BackwardSolution)
		if solver.PenaltyMethod == pyprop.PenaltyMethod.Projection and size(solver.GoodBadRatio) > 1:
			h5file.createArray(datasetPath, "GoodBadRatio", solver.GoodBadRatio)
		h5file.createArray(datasetPath, "ControlAtMaxYield", solver.ControlVectorsMax)
		h5file.createArray(datasetPath, "ForwardSolutionAtMaxYield", solver.ForwardSolutionMax)
			
	finally:
		h5file.close()


def LaTeXFigureSettings(fig_width_pt = 345, subFig=1):
	#fig_width_pt = 345.0  # Get this from LaTeX using \showthe\columnwidth
	inches_per_pt = 1.0/72.27               # Convert pt to inch
	golden_mean = (sqrt(5)-1.0)/2.0         # Aesthetic ratio
	fig_width = fig_width_pt*inches_per_pt  # width in inches
	fig_height = fig_width*golden_mean      # height in inches
	fig_size =  [fig_width,fig_height]
	if subFig.__class__ == tuple:
		fig_size = [fig_width * subFig[0], fig_height * subFig[1]]
	params = {'backend': 'ps',
			  'axes.labelsize': 12,
			  'text.fontsize': 12,
			  'legend.fontsize': 12,
			  'xtick.labelsize': 10,
			  'ytick.labelsize': 10,
			  'text.usetex': True,
			  'figure.figsize': fig_size}
	pylab.rcParams.update(params)

