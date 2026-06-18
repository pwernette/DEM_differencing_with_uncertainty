/*
 * This program is intended to compute the probability that two surfaces are significantly different,
 * while accounting for a spatially variable error in both surfaces.
 *
 * Copyright 2018: Dr. Phil Wernette (wernette@uwindsor.ca)
 */

#include <chrono>
#include <random>
#include "datastruct.hpp"

using namespace std;

int main(){
	// initialize empty Parameters and Header objects
	Params prms;
	Header hdr1, hdre1, hdr2, hdre2, hdr, prob_hdr;

	// initialize empty Raster objects
//	Raster s1, se1, s2, se2, orast, prob;
	Raster s1, se1, s2, se2;
	OutRaster orast;

	// load parameters for the program (from "params.ini" file)
	if (!prms.Initialize()) return false;

	// load header info for surfaces and error surfaces
	if (!hdr1.Initialize(prms.input1)) return false;
	if (!s1.Initialize(prms.input1, hdr1)) return false;
	if (!hdre1.Initialize(prms.error1)) return false;
	if (!se1.Initialize(prms.error1, hdre1)) return false;
	if (!hdr2.Initialize(prms.input2)) return false;
	if (!s2.Initialize(prms.input2, hdr2)) return false;
	if (!hdre2.Initialize(prms.error2)) return false;
	if (!se2.Initialize(prms.error2, hdre2)) return false;

//	cout << static_cast<int>(se2.val.size()) << " :: " << se2.val[70000] << endl;

//	s1.add(2.5);

	// generate output raster from input header files
	hdr = hdr1;						// copy header information from surface 1
	hdr.description = ("change " + prms.input1 + "_" + prms.input2);		// update description of output raster
	orast.rsize(s1.val.size());		// resize output raster to accommodate all values
	orast.copyxy(s1, s2);			// copy X coordinate information to output raster vector
	fill(orast.val.begin(), orast.val.end(), -99999);				// copy raster 1 values to output raster (temporary)

	prob_hdr = hdr;
	prob_hdr.description = ("Probability of change from t0 to t1");
//	prob.rsize(s1.val.size());
//	prob.copyxy(s1, s2);
//	fill(prob.val.begin(), prob.val.end(), -99999);

	////////////////////// START DIAGNOSTICS /////////////////////
//	cout << s1.val.size() << endl;
//	cout << s1.val[37493] << endl;
//	s1.add(5.3);
//	cout << s1.val[37493] << endl;
//	cout << orast.val.size() << endl;
//	cout << orast.val[37493] << endl;
	/////////////////////  END DIAGNOSTICS  /////////////////////

	// surface subtraction
//	orast.subtract(s1, s2);
//	orast.subtract_epsilon(s1, se1, s2, se2);

	cout << "Simulating change with " << prms.nsim << " iterations per location..." << endl;

//	orast.subtract(s2, s1);								// simple surface subtraction
//	orast.pchange_vals(s1, se1, s2, se2, /*prob,*/ prms.nsim);	// simulated change values
//	prob.pchange(s1, se1, s2, se2, prms.nsim);			// probability of change


	///// TESTING /////
	orast.pchange(s1, se1, s2, se2, prms.nsim);	// simulated change values
	///// TESTING /////


//	cout << prob.val[100100] << "  FROM MAIN.CPP" << endl;
	hdr.min_max(orast.val);			// re-compute min and max values for output raster
	prob_hdr.min_max(orast.prob);		// re-compute min and max values for probability raster


	////////////////////// START DIAGNOSTICS /////////////////////
//	cout << orast.val[37493] << endl;
	/////////////////////  END DIAGNOSTICS  /////////////////////


	// write output raster
	if(hdr.writeHDR(prms.output, orast.val) &&
			hdr.writeDAT(prms.output, orast.val)){
		cout << "Successfully wrote " << prms.output << endl;
	}

	// write probability raster
	if(prob_hdr.writeHDR((prms.output + "_probability"), orast.prob) &&
			prob_hdr.writeDAT((prms.output + "_probability"), orast.prob)){
		cout << "Successfully wrote " << prms.output << "_probability" << endl;
	}



	////////////////////// START DIAGNOSTICS /////////////////////
	///// DIAGNOSTICS: test whether data is properly read into the vector
//	cout << s1.val[1913255] << endl;
//	cout << se1.val[1913255] << endl;
//	cout << s2.val[1913255] << endl;
//	cout << se2.val[1913255] << endl;

	//// DIAGNOSTICS: test rsize() functionality
//	cout << "Length (t0) = " << s1.val.size() << endl;
//	s1.rsize(25);
//	cout << "Resize successful!" << endl;
//	cout << "Length (t1) = " << s1.val.size() << endl;
	/////////////////////  END DIAGNOSTICS  /////////////////////

	return 0;

}
