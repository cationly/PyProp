import pyprop.potential
from pyprop.potential import PotentialType, StaticStorageModel
from fourierpropagator import FourierPropagatorBase
import libfourier


class CartesianRadialPropagator(FourierPropagatorBase):
	__BASE = FourierPropagatorBase

	def __init__(self, psi, transformRank):
		self.__BASE.__init__(self, psi, transformRank)

	def ApplyConfigSection(self, configSection):
		self.__BASE.ApplyConfigSection(self, configSection)

		#Force origin to zero if we use this as a radial propagator
		#otherwise force_origin_zero should be set to False
		self.ForceOriginZero = True
		if hasattr(configSection, "force_origin_zero"):
			self.ForceOriginZero = configSection.force_origin_zero
			print "Found force_origin_zero = ", self.ForceOriginZero

	def CreateDefaultFourierPotential(self):
		fourierPotentialConf = self.StaticEnergyConf(PotentialType.Static, "libfourier.RadialKineticEnergyPotential")
		fourierPotentialConf.mass = self.Mass
		fourierPotentialConf.radial_rank = self.TransformRank
		fourierPotentialConf.storage_model = StaticStorageModel.StorageBoth
		fourierPot = pyprop.potential.CreatePotentialFromSection(fourierPotentialConf, "RadialKineticEnergy", self.psi)

		return fourierPot


