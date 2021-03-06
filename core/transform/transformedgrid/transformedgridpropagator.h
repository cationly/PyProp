#ifndef TRANSFORMEDGRIDPROPAGATOR_H
#define TRANSFORMEDGRIDPROPAGATOR_H

#include "../../common.h"
#include "../../wavefunction.h"
#include "tools.h"

namespace TransformedGrid
{

template<int Rank>
class Propagator
{
private:
	blitz::Array<cplx, 2> PropagationMatrix;
	blitz::Array<cplx, 2> DiffMatrix;
	blitz::Array<double, 2> Eigenvectors;
	blitz::Array<double, 1> Eigenvalues;
	blitz::Array<cplx, 1> TempData;

	int PropagateRank;
	Parameter Param;
	int N;
	double Mass;

	void ApplyMatrix(const blitz::Array<cplx, 2> &matrix, blitz::Array<cplx, 3> &data);
		
public:
	void ApplyConfigSection(const ConfigSection &config);
	void Setup(const Parameter &param, const cplx &dt, const Wavefunction<Rank> &psi, int rank);
	void AdvanceStep(Wavefunction<Rank> &psi);
	void ApplyDifferentiationMatrix(Wavefunction<Rank> &srcPsi, Wavefunction<Rank> &dstPsi);
	blitz::Array<cplx, 2> GetPropagationMatrix() { return PropagationMatrix; }
	blitz::Array<cplx, 2> GetDifferentiationMatrix();
	blitz::Array<double, 2> GetEigenvectors() { return Eigenvectors; }
	blitz::Array<double, 1> GetEigenvalues() { return Eigenvalues; }
};

}; //Namespace

#endif


