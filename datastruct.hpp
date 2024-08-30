/*
 * datastruct.hpp
 * Copyright 2019: Dr. Phillipe Wernette (pwernett@mtu.edu)
 */

#include <math.h>
#include <fstream>
#include <iostream>
#include <vector>
#include <windows.h>
#include <random>

using namespace std;

///////////////////////////////////////////////////////////////
// PARAMETER INITIALIZATION FILE INFORMATION
///////////////////////////////////////////////////////////////
class Params
{
	public:
	//-------------------------------------------------------------------
	//  DEMs and error surfaces at times 1 and 2, plus output surface filename
	//-------------------------------------------------------------------

	string input1;
	string error1;
	string input2;
	string error2;
	string output;

	// constructor (NOT WORKING)
//	Params();

	// destructor (NOT WORKING)
//	virtual ~Params();

	bool Initialize()
	{
		if(!LoadInParameters("params.ini"))
		{
			cout << "Cannot find 'params.ini'";
			//MessageBox(NULL, "Cannot find 'params.ini'", "Error", 0);

			return false;
		}

		return true;
	};

	bool LoadInParameters(const char* iFileName);
};


///////////////////////////////////////////////////////////////
// HEADER INFORMATION
///////////////////////////////////////////////////////////////
class Header
{
public:
	string description;
	int ncols = 0; 			// number of columns
	int nlines = 0; 			// number of lines
	int npix = 0;  			// number of pixels
	int bands = 1; 			// number of bands
	int headeroffset = 0;
	string filetype;
	int datatype = 0;
	string interleave;		// data interleave format (bsq, bip, or bil)
	string sensortype;
	string coordsys;		// coordinate system information
	float xres = 0;			// resolution (x direction)
	float yres = 0;			// resolution (y direction)
	double ulx = 0;			// upper-left x coordinate
	double uly = 0;			// upper-left y coordinate
	double ymin = 999999999;
	double xmax = -99999999;
	double valmin = 99999;
	double valmax = -99999;
	string utm_zone_number;
	string utm_zone_band;
	string datum;
	string units;		// measurement units
	string proj_string;	// projection string
	//---------------------------------------------

	// constructor (NOT WORKING)
//	Header();

	// destructor (NOT WORKING)
//	virtual ~Header();

	bool Initialize(string Fname)
	{
		if(!readENVIheader((Fname + ".hdr")))
		{
			cerr << "Cannot find '" << Fname << ".hdr'";

			return false;
		}
		return true;
	};

	void defaultHeader();

	void min_max(vector<int> r);
	void min_max(vector<long int> r);
	void min_max(vector<float> r);
	void min_max(vector<double> r);

	bool readENVIheader(string Fname);

	bool writeHDR(string filename, vector<unsigned int> outdat);
	bool writeHDR(string filename, vector<int> outdat);
	bool writeHDR(string filename, vector<long int> outdat);
	bool writeHDR(string filename, vector<float> outdat);
	bool writeHDR(string filename, vector<double> outdat);

	bool writeDAT(string fname, vector<unsigned int> outdat);
	bool writeDAT(string fname, vector<int> outdat);
	bool writeDAT(string fname, vector<long int> outdat);
	bool writeDAT(string fname, vector<float> outdat);
	bool writeDAT(string fname, vector<double> outdat);
};


///////////////////////////////////////////////////////////////
// RASTER INFORMATION
///////////////////////////////////////////////////////////////
class Raster
{
public:
	float ulx = 0;
	float uly = 0;
	vector<float> x;			// x coordinate
	vector<float> y;			// y coordinate
	vector<float> val;			// z coordinate


	///// TESTING /////
	//vector<float> prob;			// probability of change (if required)
	///// TESTING /////


	// constructor (NOT WORKING)
//	Raster();

	// destructor (NOT WORKING)
//	virtual ~Raster();

	// initialization function: pulls data from input file & info from Header object
	bool Initialize(string Fname, Header hdr)
	{
		if(!readENVIdata((Fname + ".dat"), hdr))
		{
			cout << "Cannot find '" << Fname << ".dat'";

			return false;
		}

		return true;
	};

	// function to resize Raster vectors
	void rsize(int new_dim);

	// function to read ENVI .dat file: REQUIRES Header object
	bool readENVIdata(string Fname, Header hdr);

	bool copyxy(Raster r1, Raster r2);

	// function to subtract 2 rasters (r-r2)
	// Raster objects must have same grid systems
	bool subtract(Raster r1, Raster r2);

	// subtract 2 rasters using vertical epsilon bands (binary)
	// bool subtract_epsilon(Raster r1, Raster re1, Raster r2, Raster re2);

	// bool pchange(Raster t1, Raster t1e, Raster t2, Raster t2e, int nsimulations);
//	bool pchange(Raster t1, Raster t1e, Raster t2, Raster t2e, Raster prob_change, int nsimulations);
	// bool pchange_vals(Raster t1, Raster t1e, Raster t2, Raster t2e, /*Raster prob_rast,*/ int nsimulations);

//
//	void writeENVIs(string filename, Header head);
};


///////////////////////////////////////////////////////////////
// OUTRASTER INFORMATION
///////////////////////////////////////////////////////////////
class OutRaster
{
public:
	float ulx = 0;
	float uly = 0;
	vector<float> x;			// x coordinate
	vector<float> y;			// y coordinate
	vector<float> val;			// z coordinate
	vector<float> prob;			// probability of change (if required)
	// vector<float> z_score_value;  // z-score


	// constructor (NOT WORKING)
//	Raster();

	// destructor (NOT WORKING)
//	virtual ~Raster();

//	// initialization function: pulls data from input file & info from Header object
//	bool Initialize(string Fname, Header hdr)
//	{
//		if(!readENVIdata((Fname + ".dat"), hdr))
//		{
//			cout << "Cannot find '" << Fname << ".dat'";
//
//			return false;
//		}
//
//		return true;
//	};

	// function to resize Raster vectors
	void rsize(int new_dim);

	bool copyxy(Raster r1, Raster r2);

	// function to subtract 2 rasters (r-r2)
	// Raster objects must have same grid systems
	bool subtract(Raster r1, Raster r2);

	// subtract 2 rasters using vertical epsilon bands (binary)
	// bool subtract_epsilon(Raster r1, Raster re1, Raster r2, Raster re2);

	bool pchange(Raster t1, Raster t1e, Raster t2, Raster t2e);
	bool pchange(Raster t1, float t1e, Raster t2, Raster t2e);
	bool pchange(Raster t1, Raster t1e, Raster t2, float t2e);
	bool pchange(Raster t1, float t1e, Raster t2, float t2e);
//	bool pchange(Raster t1, Raster t1e, Raster t2, Raster t2e, int nsimulations);
};
