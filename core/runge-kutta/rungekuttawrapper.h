#ifndef RUNGEKUTTAWRAPPER_H 
#define RUNGEKUTTAWRAPPER_H

#include <core/common.h>
#include <core/wavefunction.h>
#include <gsl/gsl_odeiv.h>

#include <core/utility/boostpythonhack.h>

namespace RungeKutta
{

template<int Rank>
class RungeKuttaWrapper
{
public:

	RungeKuttaWrapper() {}
	virtual ~RungeKuttaWrapper() {}
	
	enum IntegratorTypes
	{
		IntegratorRK2,
		IntegratorRK4,
		IntegratorRKF45,
		IntegratorRKCK,
		IntegratorRK8PD
	};

	typedef blitz::Array<cplx, 1> DataArray1D;

	typename Wavefunction<Rank>::Ptr Psi;
	typename Wavefunction<Rank>::Ptr TempPsi;
	object MultiplyCallback;
	bool ImTime;

private:
	
	int IntegratorType;
	
	//Integrator step type
	const gsl_odeiv_step_type *IntegratorTypeObject;

	// Integrator data struct
	gsl_odeiv_system sys;

	//Integrator object
	gsl_odeiv_step *Integrator;

public:
	void ApplyConfigSection(const ConfigSection &config);
	void Setup(typename Wavefunction<Rank>::Ptr psi);
	void AdvanceStep(object callback, typename Wavefunction<Rank>::Ptr psi, typename Wavefunction<Rank>::Ptr tempPsi, cplx dt, double t);
};
}

#endif

