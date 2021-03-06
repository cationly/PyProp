from pyproplogging import GetFunctionLogger

def CreateInstanceRank(className, rank, globals=globals(), locals=locals()):
	logger = GetFunctionLogger()
	try:
		return eval("%s_%i()" % (className, rank), globals, locals)
	except Exception:
		logger.error("Could not create instance of class %s with rank " % (className, rank))
		raise
		
def CreateDistribution(config, rank=None):
	logger = GetFunctionLogger()

	#Instance Distribution class which is templated over rank
	if rank == None:
		rank = config.Representation.rank
	distrib = CreateInstanceRank("core.DistributedModel", rank)
	
	#hack in initial distribution into configuration
	#TODO: Get initial distribution from propagator
	class sec:
		pass

	if hasattr(config, "Distribution"):
		distrSection = config.Distribution
	else:
		distrSection = sec()

	if not hasattr(distrSection, "proc_array_rank"):	
		distrSection.proc_array_rank = 1
	
	#DO NOT CHANGE THIS UNLESS YOU ARE ABSOLUTELY SURE. IF THE LAST RANK IS USED
	#SaveWavefunctionHDF WILL HAVE ABSOLUTELY HORRIBLE PERFORMANCE!!!
	if not hasattr(distrSection, "initial_distribution"):
		distrSection.initial_distribution = array([0], dtype=int)

	if distrSection.initial_distribution[0] != 0:
		logger.warning("Not distributing first rank of wavefunction. Consider removing [Distribution] from the config file")

	#apply configuration
	distrib.ApplyConfigSection(distrSection)
	
	return distrib
	
	
def CreateRepresentation(config, distribution):
	logger = GetFunctionLogger()
	#Create instance
	representation = config.Representation.type()

	#Set distribution model
	logger.debug("Setting distributed model")
	representation.SetDistributedModel(distribution)
	
	#Apply configuration section
	config.Representation.Apply(representation)

	#If the representation is a base class of CombinedRepresentation,
	#we must set up the 1d sub-representations.
	combinedRepr = None
	try:
		combinedRepr = eval("core.CombinedRepresentation_" + str(config.Representation.rank))
	except:
		pass
	if combinedRepr != None and combinedRepr in config.Representation.type.__mro__:
		CreateSubRepresentations(representation, config)
	
	return representation

def CreateSubRepresentations(combinedRepr, config):
	logger = GetFunctionLogger()
	rank = config.Representation.rank
	for i in range(rank):
		sectionName = config.Representation.Get("representation" + str(i))
		logger.debug("ConfigSection for rank %i is %s" % (i, sectionName))
		section = config.GetSection(sectionName)

		#create instance
		repr = section.type()
		repr.SetBaseRank(i)
		logger.debug("Representation for rank %i is %s" % (i, repr))

		#set distributed model
		fullDistrib = combinedRepr.GetDistributedModel()
		distrib = fullDistrib.CreateSubDistributedModel()
		repr.SetDistributedModel(distrib)

		#apply configuration
		section.Apply(repr)

		#Attach this repr to the main representation
		combinedRepr.SetRepresentation(i, repr)

	
def CreateWavefunctionInstance(representation, allocateData=True):
	logger = GetFunctionLogger()
	#Create instance
	logger.debug("    Creating instance")
	rank = len(representation.GetFullShape())
	psi = CreateInstanceRank("core.Wavefunction", rank)
	
	#Set reresentation
	logger.debug("    Setting representation")
	psi.SetRepresentation(representation)
	
	#Allocate data
	if allocateData:
		logger.debug("    Allocating data")
		psi.AllocateData()
	
	return psi
	
	
def CreatePropagator(config, psi):
	#Create instance
	propagator = None
	if hasattr(config.Propagation, "propagator"):
		propagator = config.Propagation.propagator(psi)
		config.Apply(propagator)
		config.Propagation.Apply(propagator)
	else:
		logger.warning("No propagator specified in config file. Make sure your potential evaluator includes kinetic energy.")
	
	return propagator
	
	
def CreatePotential(config, potentialName, psi):
	potentialConfig = config.GetSection(potentialName)
	return CreatePotentialFromSection(potentialConfig, potentialName, psi)

def CreatePotentialFromSection(potentialConfig, potentialName, psi):
	potential = None
	if potentialConfig.type == PotentialType.Static:
		potential = StaticPotentialWrapper(psi)

	elif potentialConfig.type == PotentialType.Dynamic:
		potential = DynamicPotentialWrapper(psi)
	
	elif potentialConfig.type == PotentialType.FiniteDifference:
		potential = FiniteDifferencePotentialWrapper(psi)
		
	elif potentialConfig.type == PotentialType.CrankNicholson:
		potential = CrankNicholsonPotentialWrapper(psi)
	
	elif potentialConfig.type == PotentialType.Matrix:
		potential = MatrixPotentialWrapper(psi)
	
	elif potentialConfig.type == PotentialType.RankOne:
		potential = RankOnePotentialWrapper(psi)
	
	else:
		raise "Unknown potential type", potentialConfig.type

	potentialConfig.Apply(potential)
	potential.Name = potentialName
	return potential

	
