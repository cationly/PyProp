#ifndef BLITZTRANSPOSE_H
#define BLITZTRANSPOSE_H

#include "../common.h"
#include "../utility/blitzutils.h"
#include "blitzmpi.h"

#include <mpi.h>
#include <vector>

template<int DataRank>
class ArrayTranspose
{
public:
	typedef blitz::Array<cplx, DataRank> DataArray;
	typedef blitz::Array<int, 1> ProcVector;
	typedef blitz::Array<bool, 1> ProcVectorBool;
	typedef blitz::Array<MPI_Comm, 1> ProcVectorComm;
	typedef blitz::TinyVector<int, DataRank> DataVector;

private:
	//The Communicator for the entire cartesian grid
	int ProcRank;
	MPI_Comm CartesianComm;         //(local)  Communicator for the virtual topology
	ProcVector CartesianCoord;		//(local)  Location of this proc in the cartesian topology
	int CartesianRank;				//(local)  MPI Rank in the topology communicator
	ProcVector CartesianShape;      //(global) Shape of cartesian topology

	//(local) Communicators to communicate with the other procs along the ProcRank different directions
	//In the cartesian topology
	ProcVectorComm GroupComm;
	ProcVector GroupRank;

	//MPI_COMM_WORLD Rank and Size
	int WorldRank;
	int WorldSize;
	
public:
	ArrayTranspose(int procRank);
	~ArrayTranspose();
	
	//Accessors 
	const ProcVector& GetProcGridShape()
	{
		return CartesianShape;
	}

	void Transpose(const DataVector &fullShape, DataArray &inData, const ProcVector &inDistr, DataArray &outData, const ProcVector &outDistr);
	void Transpose(const DataVector &fullShape, const ProcVector &fullDistr, DataArray &inData, int inDistr, DataArray &outData, int outDistr, int procRank);

	/*
	 * Creates a local shape which matches a given shape of the virtual global array for a given distribution
	 * on the proc grid defined by this class
	 */
	DataVector CreateDistributedShape(const DataVector &fullShape, const ProcVector &distrib)
	{
		return CreateDistributedShape(fullShape, distrib, GroupRank);
	}
	
	DataVector CreateDistributedShape(const DataVector &fullShape, const ProcVector &distrib, const ProcVector &groupRank)
	{
		DataVector distrShape = fullShape;
		for (int i=0; i<ProcRank; i++)
		{
			int rank = distrib(i);
			distrShape(rank) = CreateDistributedShape(fullShape(rank), i, groupRank(i));
		}
		return distrShape;
	}

	/*
	 * Extends fullshape to a shape big enough to be distributed over distrib
	 */
	DataVector CreatePaddedShape(const DataVector &fullShape, const ProcVector &distrib)
	{
		DataVector paddedShape = fullShape;
		for (int i=0; i<ProcRank; i++)
		{
			int rank = distrib(i);
			paddedShape(rank) = CreatePaddedShape(fullShape(rank), i);
		}
		return paddedShape;
	}

	int CreatePaddedShape(int fullShape, int procRank)
	{
		int rest = fullShape % CartesianShape(procRank);
		if (rest != 0)
		{
			fullShape += CartesianShape(procRank) - rest;
		}
		return fullShape;
	}

	int CreateDistributedShape(int fullShape, int procRank)
	{
		return CreateDistributedShape(fullShape, procRank, GroupRank(procRank));
	}

	/*
	 * Parameters:
	 *   fullShape: shape of a 1D array on the whole domain
	 *   procRank: along which rank of the proc array we should distribute this array
	 *   groupRank: pretend to have this rank in the proc group when calculating the 
	 *              distributed size instead of GroupRank(procRank).
	 */
	int CreateDistributedShape(int fullShape, int procRank, int groupRank)
	{
		int rest = fullShape % CartesianShape(procRank);
		int distrShape;
		if (rest == 0) 
		{
			distrShape = fullShape / CartesianShape(procRank);
		}
		else
		{
			int paddedShape = CreatePaddedShape(fullShape, procRank);
			int paddedDistrShape = paddedShape / CartesianShape(procRank);
			int shape = fullShape - paddedDistrShape * groupRank;
			shape = std::max(shape, 0);
			shape = std::min(shape, paddedDistrShape);
			distrShape = shape;	
		}
				
		return distrShape;
	}


	int GetLocalStartIndex(int globalSize, int procRank)
	{
		int paddedShape = CreatePaddedShape(globalSize, procRank);
		int paddedDistribShape = CreateDistributedShape(paddedShape, procRank);
		return CartesianCoord(procRank) * paddedDistribShape;
	}

	blitz::Range GetLocalRange(int globalSize, int procRank)
	{
		int startIndex = GetLocalStartIndex(globalSize, procRank);
		int distribShape = CreateDistributedShape(globalSize, procRank);
		return blitz::Range(startIndex, startIndex + distribShape - 1);	
	}

	/*
	 * Creates a test-array such that each cell in the array will have its value equal to its
	 * index in the virtual global array. It has no other purpose than to help verify the 
	 * correctness of 
	 */
	DataArray CreateReferenceData(const DataVector &fullShape, const ProcVector &distrib)
	{
		DataVector paddedShape = CreatePaddedShape(fullShape, distrib);
		DataVector paddedDistribShape = CreateDistributedShape(paddedShape, distrib);

		/*
		for (int i=0;i<WorldSize;i++) {
			if (WorldRank == i) 
			{
				cout << "ProcId = " << WorldRank << endl;
				cout << "  " << paddedShape << endl;
				cout << "  " << CreateDistributedShape(fullShape, distrib);
				cout << endl;
			}
			MPI_Barrier(MPI_COMM_WORLD);
		}		
		*/
		
		DataArray data(CreateDistributedShape(fullShape, distrib));
	
		DataVector startPos(0);
		for (int i=0; i<ProcRank; i++)
		{
			int rank = distrib(i);
			startPos(rank) = CartesianCoord(i) * paddedDistribShape(rank);
		}

		typename DataArray::iterator it = data.begin();
		for (int linearCount=0; linearCount<data.size(); linearCount++)
		{
			DataVector pos = it.position();
			pos += startPos;
			*it = CoordToIndex(fullShape, pos);
			it++;
		}

		return data;
	}

};

template<int DataRank>
ArrayTranspose<DataRank>::ArrayTranspose(int procRank) : ProcRank(procRank) 
{
	CartesianCoord.resize(ProcRank);
	CartesianShape.resize(ProcRank);
	GroupComm.resize(ProcRank);
	GroupRank.resize(ProcRank);

	CartesianCoord = 0;
	CartesianShape = 0;
	GroupComm = 0;
	GroupRank = 0;

	MPI_Comm_rank(MPI_COMM_WORLD, &WorldRank);
	MPI_Comm_size(MPI_COMM_WORLD, &WorldSize);

	ProcVector periods;
	periods.resize(ProcRank);
	periods = 0;
	
	//Set up size of dimensions. Currently, let MPI decide
	MPI_Dims_create(WorldSize, ProcRank, CartesianShape.data());	

#if false
	if (WorldRank == 0)
	{
		cout << "Creating " << ProcRank << "dimensional cratesian process grid" << endl;
		cout << "  Dims = " << CartesianShape << endl;
		cout << endl;
	}
#endif

	//Create cartesian communicator
	MPI_Cart_create(MPI_COMM_WORLD, ProcRank, CartesianShape.data(), periods.data(), 0, &CartesianComm);
	//Get rank and coord from cartesian comm
	MPI_Comm_rank(CartesianComm, &CartesianRank);
	MPI_Cart_coords(CartesianComm, CartesianRank, ProcRank, CartesianCoord.data());

	//Set up communicators on each slice of the processor array from the current coordinate.
	for (int i=0; i<ProcRank; i++)
	{
		//Use color as the coordinate of the current proc, and set 
		//the coordinate along the i'th axis to zero, to get the same color
		//for all procs along that direction 
		ProcVector colorCoord = CartesianCoord.copy();
		colorCoord(i) = 0;
		//We cannot use vector as a key, so, create an index to this vector
		//int the global cartesian proc grid
		int color = CoordToIndex(CartesianShape, colorCoord);
		int key = CartesianCoord(i);

		//split into communicators pr color.
		MPI_Comm_split(CartesianComm, color, key, &GroupComm(i));
		MPI_Comm_rank(GroupComm(i), &GroupRank(i));
	}
}

template<int DataRank>
ArrayTranspose<DataRank>::~ArrayTranspose()
{
	for (int i=0; i<ProcRank; i++)
	{
		MPI_Comm_free(&GroupComm(i));	
	}
	MPI_Comm_free(&CartesianComm);
}


/*
 * Transposes inData, which is distributed along S1 = inDistr 
 * to be distributed along S2 = outDistr, and stored in outData
 */
template<int DataRank>
void ArrayTranspose<DataRank>::
Transpose(const DataVector &fullShape, DataArray &inData, const ProcVector &inDistr, DataArray &outData, const ProcVector &outDistr)
{
	typedef std::vector<int> vectori;

	vectori procRank;
	vectori fromRank;
	vectori toRank;
	
	//Create a list of things to do...
	for (int i=0; i<ProcRank; i++)
	{
		if (inDistr(i) != outDistr(i))
		{
			procRank.push_back(i);
			fromRank.push_back(inDistr(i));
			toRank.push_back(outDistr(i));
		}
	}
	
	if (procRank.size() == 0)
	{
		cout << "Warning: Nothing to do transforming " << inDistr << " to " << outDistr << endl;
		return;
	}
	if (procRank.size() > 1)
	{
		throw std::runtime_error("Currently only supporting changing one rank pr. call to transpose");
	}
	
	Transpose(fullShape, inDistr, inData, fromRank[0], outData, toRank[0], procRank[0]);
}

template<int DataRank>
void ArrayTranspose<DataRank>::
Transpose(const DataVector &fullShape, const ProcVector &fullDistr, DataArray &inData, int inDistr, DataArray &outData, int outDistr, int procRank)
{
	ProcVector outFullDistr = fullDistr.copy();
	outFullDistr(procRank) = outDistr;
		
	//Size of the processor rank we're working on
	int Np = CartesianShape(procRank);
	int curProc = GroupRank(procRank);
	
	//Full sizes
	int inSizeFull = fullShape(inDistr);
	int outSizeFull = fullShape(outDistr);
	DataVector inPaddedShape = CreatePaddedShape(fullShape, fullDistr);

	//Local (distributed) sizes
	int outSizeDistr = CreateDistributedShape(outSizeFull, procRank);
	DataVector inDistrShape = inData.shape() ;//  CreateDistributedShape(inPaddedShape, fullDistr);

	//Temporary (padded) sizes
	int tempSizeFull = CreatePaddedShape(outSizeFull, procRank);
	int sendSize = tempSizeFull / Np;
	int recvSize = CreatePaddedShape(inSizeFull, procRank) / Np;

	//Check array sizes
	DataVector outputShape = inData.shape();
	outputShape(inDistr) = inSizeFull;
	outputShape(outDistr) = outSizeDistr;
	if (outputShape != outData.shape())
	{
		throw std::runtime_error("Invalid shape of output data. Got " + ToString(outData.shape()) + ", expected " + ToString(outputShape));
	}

	DataVector index(0);
	DataVector sendBufferShape(1);
	sendBufferShape(outDistr) = tempSizeFull;
	DataArray sendBuffer(sendBufferShape);

	DataVector recvBufferShape(1);
	recvBufferShape(outDistr) = sendSize;
	recvBufferShape(inDistr) = Np;
	DataArray recvBuffer(recvBufferShape);

	DataVector inShape = inData.shape();

	//Distributed Shape on the other procs
	typedef blitz::Array<DataVector, 1> ShapeArray;
	ProcVector groupRank = GroupRank.copy();
	ShapeArray inDistrShapeProc(Np);
	ShapeArray outDistrShapeProc(Np);
	for (int i=0; i<Np; i++)
	{
		groupRank(procRank) = i;
		inDistrShapeProc(i) = CreateDistributedShape(fullShape, fullDistr, groupRank);
		outDistrShapeProc(i) = CreateDistributedShape(fullShape, outFullDistr, groupRank);
#if false
		if (WorldRank == 0)
		{
			cout << "groupRank = " << ToString(groupRank) << endl;
			cout << "in shape  " << i << " = " << ToString2(inDistrShapeProc(i)) << endl;
			cout << "out shape " << i << " = " << ToString2(outDistrShapeProc(i)) << endl;
		}
		MPI_Barrier(MPI_COMM_WORLD);
#endif 
	}


	for (int i=0; i<Np; i++)
	{
		DataArray recvView;
		MPI_Request recvRequest;
		MPI_Request sendRequest;
		bool recvActive = false;
		bool sendActive = false;
			
		//which procs to send or recv from
		int toProc = (i + curProc) % Np;
		int fromProc = (Np - i + curProc) % Np;

		int toProcStart = sendSize * toProc;
		int toProcSize =  CreateDistributedShape(outSizeFull, procRank, toProc);
		
		int fromProcStart = recvSize * fromProc;
		int fromProcSize = CreateDistributedShape(inSizeFull, procRank, fromProc);

#if false
		for (int i=0; i<Np; i++)
		{
			if (curProc == i)
			{
				cout << "Proc " << curProc << endl
					 << "  toProc   = " << toProc << endl
					 << "  fromProc = " << fromProc << endl
					 << "  toProcStart   = " << toProcStart << endl
					 << "  toProcSize    = " << toProcSize << endl
					 << "  fromProcStart = " << fromProcStart << endl
					 << "  fromProcSize  = " << fromProcSize << endl
					 ;

			}
			MPI_Barrier(MPI_COMM_WORLD);
		}
#endif

		//read
		if (toProcSize > 0 && inData.size() > 0)
		{
			DataVector lboundRead(0);
			DataVector uboundRead(inData.shape());
			lboundRead(outDistr) = toProcStart;
			uboundRead(outDistr) = toProcStart + toProcSize;
			uboundRead -= 1;
			blitz::RectDomain<DataRank> readDomain(lboundRead, uboundRead);

			DataArray sendView = inData(readDomain);
			BlitzMPI<cplx, DataRank> sendMPI(sendView);

#if false
			for (int i=0; i<Np; i++)
			{
				if (curProc == i)
				{
					cout << "Proc " << curProc << endl
						 << "  send start  = " << ToString2(lboundRead)  << endl
						 << "  send end    = " << ToString2(uboundRead)  << endl
						 << "  send data   = " << sendView << endl;
						 ;
	
				}
				MPI_Barrier(MPI_COMM_WORLD);
			}
#endif
		
			sendRequest = sendMPI.ISend(sendView, toProc, 0, GroupComm(procRank));
			sendActive = true;
		}
	
		//recv
		if (fromProcSize > 0 && outData.size() > 0)
		{
			DataVector lboundRecv(0);
			DataVector uboundRecv(outData.shape());
			lboundRecv(inDistr) = fromProcStart;
			uboundRecv(inDistr) = fromProcStart + fromProcSize;
			uboundRecv -= 1;
			blitz::RectDomain<DataRank> recvDomain(lboundRecv, uboundRecv);

			recvView.reference(outData(recvDomain));
			BlitzMPI<cplx, DataRank> recvMPI(recvView);

#if false
			for (int i=0; i<Np; i++)
			{
				if (curProc == i)
				{
					cout << "Proc " << curProc << endl
						 << "  recv start  = " << ToString2(lboundRecv)  << endl
						 << "  recv end    = " << ToString2(uboundRecv)  << endl
						 ;
	
				}
				MPI_Barrier(MPI_COMM_WORLD);
			}
#endif

			recvRequest = recvMPI.IRecv(recvView, fromProc, 0, GroupComm(procRank));
			recvActive = true;
		}


		if (sendActive)
		{
			MPI_Status status;
			MPI_Wait(&sendRequest, &status);
		}
	
		if (recvActive)
		{
			MPI_Status status;
			MPI_Wait(&recvRequest, &status);
#if false
			for (int i=0; i<Np; i++)
			{
				if (curProc == i)
				{
					cout << "Proc " << curProc << endl
						 << "  recv data   = " << outData << endl;
						 ;
	
				}
				MPI_Barrier(MPI_COMM_WORLD);
			}
#endif
		}	
		MPI_Barrier(MPI_COMM_WORLD);
	}

}

#endif
