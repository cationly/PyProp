#ifndef TRANSFORMEDGRIDPROPAGATOR_H
#define TRANSFORMEDGRIDPROPAGATOR_H

#include "../common.h"
#include "../wavefunction.h"
#include "transformedgrid/tools.h"

namespace TransformedGrid
{

template<int Rank>
class Propagator
{
private:
	blitz::Array<cplx, 2> PropagationMatrix;
	blitz::Array<cplx, 1> TempData;

	int PropagateRank;
	Parameter Param;
	int N;

	void ApplyPropagationMatrix(blitz::Array<cplx, 2> data);
		
public:
	void Setup(const Parameter &param, const cplx &dt, const Wavefunction<Rank> &psi, int rank);
	void AdvanceStep(Wavefunction<Rank> &psi);
};

}; //Namespace

#endif


