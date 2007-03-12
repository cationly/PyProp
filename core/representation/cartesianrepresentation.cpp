#include "cartesianrepresentation.h"
#include "../wavefunction.h"

//Implementation of the Representation interface.
template<int Rank>
blitz::TinyVector<int, Rank> CartesianRepresentation<Rank>::GetFullShape()
{
	blitz::TinyVector<int, Rank> fullShape;
	for (int i=0;i<Rank;i++)
	{
		fullShape(i) = Range(i).Count;
	}
	return fullShape;
}

template<int Rank>
cplx CartesianRepresentation<Rank>::InnerProduct(const Wavefunction<Rank> &w1, const Wavefunction<Rank> &w2)
{
	double weight = 1;
	for (int i=0; i<Rank; i++)
	{
		weight *= Range(i).Dx;
	}
	
	return sum(conj(w1.Data) * w2.Data) * weight;
}

template <int Rank>
void CartesianRepresentation<Rank>::ApplyConfigSection(const ConfigSection &cfg)
{
	//Check that the rank specified in the config file is prop
	int configRank = 0;
	cfg.Get("rank", configRank);
	
	if (configRank != Rank)
	{
		std::cout << "Invalid rank (" << configRank << ") "
				<< "specified for CartesianRange<" << Rank << ">" << std::endl;
		exit(-1);
	}

	//Get range	
	for (int i=0; i<Rank; i++)
	{
		int globalRank = i + this->GetBaseRank();

		blitz::TinyVector<double, 3> rangeVector;
		std::string settingName = "rank" + ToString(globalRank);
		cfg.Get(settingName, rangeVector);
		
		double min = rangeVector(0);
		double max = rangeVector(1);
		int count = (int)rangeVector(2);
		
		Range(i) = CartesianRange(min, max, count);
	}
}

template class CartesianRepresentation<1>;
template class CartesianRepresentation<2>;
template class CartesianRepresentation<3>;
template class CartesianRepresentation<4>;
template class CartesianRepresentation<5>;
template class CartesianRepresentation<6>;
template class CartesianRepresentation<7>;
template class CartesianRepresentation<8>;
template class CartesianRepresentation<9>;