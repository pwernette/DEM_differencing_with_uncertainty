/*
 * This program is intended to compute the probability that two surfaces are significantly different,
 * while accounting for a spatially variable error in both surfaces.
 *
 * Copyright 2019: Dr. Phillipe Wernette (pwernett@mtu.edu)
 * TO DO:
 *  1) Add option to specify global error value for raster 1 and/or 2 -> to be used in OutRaster::pchange function
 *  2) Add additional outputs as (a) Z-score and (b) t-score
 *     Z = (mu2-mu1)/(sqrt(pow(2.0,sd1)+pow(2.0,sd2)))
 */

#include <chrono>
#include <random>
#include "datastruct.hpp"
#include <boost/lexical_cast.hpp>

using namespace std;

// C++11 WITH boost: Function to check if an input is a number -> returns TRUE if a number; returns FALSE if NOT a number
bool isFloat(const std::string &somestring){
	using boost::lexical_cast;
	using boost::bad_lexical_cast;

	try{
		boost::lexical_cast<float>(somestring);
	}
	catch (bad_lexical_cast &){
		return false;
	}

	return true;
}

int main(){

	// initialize empty Parameters and Header objects
	Params prms;
	Header hdr1, hdre1, hdr2, hdre2, hdr, prob_hdr;
	// Header hdr1, hdr2, hdr, prob_hdr;

	// initialize empty Raster objects
	// Raster s1, se1, s2, se2, orast, prob; // OLD APPROACH
	Raster s1, se1, s2, se2; //--> WORKING
	// Raster s1, s2;
	OutRaster orast;

	// initialize float error raster values
	float se1_val, se2_val;

	// load parameters for the program (from "params.ini" file)
	if(!prms.Initialize()) return false;

	// Check if error raster(s) is/are a simple float input
	bool se1_num = isFloat(prms.error1);
	bool se2_num = isFloat(prms.error2);
	// bool se1_num = TRUE;
	// bool se2_num = TRUE;
	cout << se1_num << endl;
	cout << se2_num << endl;

	// load header info for surfaces and error surfaces
	// SURFACE at T0
	if(!hdr1.Initialize(prms.input1)) return false;
	if(!s1.Initialize(prms.input1, hdr1)) return false;

	// SURFACE at T1
	if(!hdr2.Initialize(prms.input2)) return false;
	if(!s2.Initialize(prms.input2, hdr2)) return false;

	// ERROR SURFACE at T0
	if (!se1_num){
		cout << "Attempting to load error raster: " << prms.error1 << endl;

		// Create header and raster objects to attempt to read in a raster
		// Header hdre1;
		// Raster se1;

		// Attempt to read header and .dat files
		if(!hdre1.Initialize(prms.error1)) return false;
		if(!se1.Initialize(prms.error1, hdre1)) return false;
	} else{
		se1_val = stof(prms.error1); // else, assign se1 as a float based on the value of prms.error1
		cout << "Global uncertainty value detected. Setting uncertainty for t0 = " << se1_val << endl;

		// Since the uncertainty is a global value, remove the first uncertainty raster and header
		// delete(hdre1);
		// delete(se1);
	}

	// ERROR SURFACE at T1
	if (!se2_num){
		cout << "Attempting to load error raster: " << prms.error2 << endl;

		// Create header and raster objects to attempt to read in a raster
		// Header hdre2;
		// Raster se2;

		// Attempt to read header and .dat file
		if(!hdre2.Initialize(prms.error2)) return false;
		if(!se2.Initialize(prms.error2, hdre2)) return false;
	} else{
		se2_val = stof(prms.error2); // else, assign se2 as a float based on the value of prms.error2
		cout << "Global uncertainty value detected. Setting uncertainty for t1 = " << se2_val << endl;

		// Since the uncertainty is a global value, remove the second uncertainty raster and header
		// delete(hdre2);
		// delete(se2);
	}
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

	////////////////////// START DIAGNOSTICS /////////////////////
	//	cout << s1.val.size() << endl;
	//	cout << s1.val[37493] << endl;
	//	s1.add(5.3);
	//	cout << s1.val[37493] << endl;
	//	cout << orast.val.size() << endl;
	//	cout << orast.val[37493] << endl;
	/////////////////////  END DIAGNOSTICS  /////////////////////

	cout << "testing A" << endl;
	///// TESTING /////
	if(!se1_num && !se2_num){
		cout << "  testing A1" << endl;
		orast.pchange(s1, se1, s2, se2);	// simulated change values
		// orast.pchange(s1, se1, s2, se2, prms.nsim);	// simulated change values
		cout << "  testing A1 good" << endl;
	} else if(se1_num && !se2_num){
		cout << "  testing A2" << endl;
		orast.pchange(s1, se1_val, s2, se2);	// simulated change values
		cout << "  testing A2 good" << endl;
	} else if(!se1_num && se2_num){
		cout << "  testing A3" << endl;
		orast.pchange(s1, se1, s2, se2_val);	// simulated change values
		cout << "  testing A3 good" << endl;
	} else{
		cout << "  testing A4" << endl;
		orast.pchange(s1, se1_val, s2, se2_val);	// simulated change values
		cout << "  testing A4 good" << endl;
	}
	///// TESTING /////
	// cout << "testing B" << endl;

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

	// write z-score raster
	// if(prob_hdr.writeHDR((prms.output + "_z_score"), orast.z_score_value) &&
	// 		prob_hdr.writeDAT((prms.output + "_z_score"), orast.z_score_value)){
	// 	cout << "Successfully wrote " << prms.output << "_z_score" << endl;
	// }



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
