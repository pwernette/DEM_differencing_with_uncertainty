#include <iostream>
#include <fstream>
#include <random>
#include <algorithm>
#include <ctime>
#include <cmath>
#include <chrono>

#include "datastruct.hpp"

using namespace std;


///////////////////////////////////////////////////////////////
// PARAMETER DEFAULTS AND FUNCTIONS
///////////////////////////////////////////////////////////////

// constructor
//Params::Params();

// destructor
//Params::~Params();

//this function loads in the parameters from a given file name. Returns
//false if there is a problem opening the file.
bool Params::LoadInParameters(const char* iFileName)
{
  ifstream grab(iFileName);

  //check file exists
  if (!grab)
  {
	cerr << "ERROR: Cannot open " << iFileName << endl;
    return false;
  }

  //load in from the file
  char ParamDescription[40];

  grab >> ParamDescription;
  grab >> input1;
  grab >> ParamDescription;
  grab >> error1;
  grab >> ParamDescription;
  grab >> input2;
  grab >> ParamDescription;
  grab >> error2;
  grab >> ParamDescription;
  grab >> output;
  grab >> ParamDescription;
  grab >> nsim;

  return true;
}


///////////////////////////////////////////////////////////////
// HEADER DEFAULTS AND FUNCTIONS
///////////////////////////////////////////////////////////////
//int Header::ncols = 0;
//int Header::nlines = 0;
//int Header::bands = 1;
//int Header::headeroffset = 0;
//int Header::datatype = 0;
//float Header::xres = 0;
//float Header::yres = 0;
//double Header::ulx = 0;
//double Header::uly = 0;
//double Header::ymin = 999999999;
//double Header::xmax = -99999999;
//double Header::valmin = 99999;
//double Header::valmax = -99999;

// constructor
//Header::Header();

// destructor
//Header::~Header();

void Header::min_max(vector<int> r){
	vector<int> rr = r;

//	cout << rr[4141] << endl;

	sort(rr.begin(), rr.end());

	rr.erase(remove(rr.begin(), rr.end(), -9999), rr.end());
	rr.erase(remove(rr.begin(), rr.end(), -99999), rr.end());

	Header::valmax = rr.back();
//	cout << Header::valmax << endl;

	Header::valmin = rr.front();
//	cout << Header::valmin << endl;
}
void Header::min_max(vector<long int> r){
	vector<long int> rr = r;

//	cout << rr[4141] << endl;

	sort(rr.begin(), rr.end());

	rr.erase(remove(rr.begin(), rr.end(), -9999), rr.end());
	rr.erase(remove(rr.begin(), rr.end(), -99999), rr.end());

	Header::valmax = rr.back();
//	cout << Header::valmax << endl;

	Header::valmin = rr.front();
//	cout << Header::valmin << endl;
}
void Header::min_max(vector<float> r){
	vector<float> rr = r;

//	cout << rr[4141] << endl;

	sort(rr.begin(), rr.end());

	rr.erase(remove(rr.begin(), rr.end(), -9999), rr.end());
	rr.erase(remove(rr.begin(), rr.end(), -99999), rr.end());

	Header::valmax = rr.back();
//	cout << Header::valmax << endl;

	Header::valmin = rr.front();
//	cout << Header::valmin << endl;
}
void Header::min_max(vector<double> r){
	vector<double> rr = r;

//	cout << rr[4141] << endl;

	sort(rr.begin(), rr.end());

	rr.erase(remove(rr.begin(), rr.end(), -9999), rr.end());
	rr.erase(remove(rr.begin(), rr.end(), -99999), rr.end());

	Header::valmax = rr.back();
//	cout << Header::valmax << endl;

	Header::valmin = rr.front();
//	cout << Header::valmin << endl;
}

////this function loads in the parameters from a given file name. Returns
////false if there is a problem opening the file.
bool Header::readENVIheader(string filename){
	string fn = filename;

	register int i;
	string line;

	// attempt to open specified input file
	ifstream infile(filename.c_str(), ios::in);
	if(!infile){
		cerr << "ERROR: Cannot open " << filename << endl;
		return false;
	}

	cout << "Reading information from " << filename.c_str() << "..." << endl;

	while(getline(infile, line)){
		// split the identifier from the information
		string item = line.substr(0, (line.find_first_of("="))-1);

		// get description of raster
		if(item.compare("description") == 0){
			Header::description = line.substr(line.find_first_of("{"), line.find_first_of("}"));
		}

		//get number of columns (aka: samples) in raster
		if(item.compare("samples") == 0){
			Header::ncols = atoi(line.substr(line.find_first_of("=")+2, line.length()-1).c_str());
			//cout << header.ncols << endl;
		}

		// get number of lines in raster
		if(item.compare("lines") == 0){
			Header::nlines = atoi(line.substr(line.find_first_of("=")+2, line.length()-1).c_str());
			//cout <<  header.nlines << endl;
		}

		// get number of bands
		if(item.compare("bands") == 0){
			Header::bands = atoi(line.substr(line.find_first_of("=")+2, line.length()-1).c_str());
		}

		// header offset information
		if(item.compare("header offset") == 0){
			Header::headeroffset = atoi(line.substr(line.find_first_of("=")+2, line.length()-1).c_str());
		}

		//get file type info
		if(item.compare("file type") == 0){
			Header::filetype = line.substr(line.find_first_of("=")+2, line.length()-1);
		}

		// get data type
		if(item.compare("data type") == 0){		// e.g 5 = double
			Header::datatype = atoi(line.substr(line.find_first_of("=")+2, line.length()-1).c_str());
		}

		// get interleave format
		if(item.compare("interleave") == 0){		// "BSQ" | "BIL" | "BIP"
			Header::interleave = line.substr(line.find_first_of("=")+2, line.length()-1);
		}

		// get sensor type
		if(item.compare("sensor type") == 0){
			Header::sensortype = line.substr(line.find_first_of("=")+2, line.length()-1);
		}

		// get map information (i.e. coordinate and projection information
		if(item.compare("map info") == 0){
			// *DIAGNOSTIC PURPOSES* -> output item and line information
			//cout << item << endl;
			//cout << line << endl;

			// get coordinate system info
			size_t com = line.find_first_of("{")+1;
			size_t com2 = line.find(",", com+1);
			Header::coordsys = line.substr(com, com2-com);

			// get upper-left x coordinate
			com = line.find(",", com2);
			com2 = line.find(",", com+1);
			com = line.find(",", com2);
			com2 = line.find(",", com+1);
			com = line.find(",", com2);
			com2 = line.find(",", com+1);
			Header::ulx = atof((line.substr(com+2, com2-com)).c_str());

			// get upper-left y coordinate
			com = line.find(",", com2);
			com2 = line.find(",", com+1)-2;
			Header::uly = atof((line.substr(com+2, com2-com)).c_str());

			// get spatial resolution in the x direction
			com = line.find(",", com2);
			com2 = line.find(",", com+1)-2;
			Header::xres = atof((line.substr(com+2, com2-com)).c_str());

			// get spatial resolution in the y direction
			com = line.find(",", com2);
			com2 = line.find(",", com+1)-2;
			Header::yres = atof((line.substr(com+2, com2-com)).c_str());

			// get UTM zone and band combination (if UTM coordinate system)
			if(Header::coordsys.compare("UTM") == 0){
				// extract the UTM zone number
				com = line.find(",", com2);
				com2 = line.find(",", com+1)-2;
				Header::utm_zone_number = (line.substr(com+2, com2-com));

				// extract the UTM zone band
				com = line.find(",", com2);
				com2 = line.find(",", com+1)-2;
				Header::utm_zone_band = (line.substr(com+2, com2-com));
			}

			// get datum information
			com = line.find(",", com2);
			com2 = line.find(",", com+1)-2;
			Header::datum = (line.substr(com+2, com2-com));

			// get map units
			com = line.find("units=", com2)+6;
			com2 = line.find_last_of("}");
			Header::units = (line.substr(com, com2-com));
		}

		// get projection string information
		if(item.compare("coordinate system string") == 0){
			Header::proj_string = line.substr(line.find_first_of("{")+1, line.find_first_of("}")-line.find_first_of("{")-1);
		}
	}

	// compute total number of pixels
	Header::npix = Header::ncols * Header::nlines;
	Header::xmax = -99999;
	Header::ymin = 9999999999;

	infile.close();

	return true;
}

bool Header::writeHDR(string filename, vector<unsigned int> outinfo){
	string tmp = filename.append(".hdr");

	// initialize the file pointer
	FILE *wrhead;

	// open the file
	wrhead = fopen(tmp.c_str(), "w");
	if(!wrhead){
		cerr << "ERROR: Cannot write " << tmp.c_str() << endl;
		exit(1);
	}

//	dattype = datout(outinfo);

	Header::interleave = "bsq";

	// write the ascii header file
	(void) fprintf(wrhead, "ENVI\n");
	(void) fprintf(wrhead, "description = {%s}\n", filename); // file description
	(void) fprintf(wrhead, "samples = %i\n", Header::ncols); // number of columns
	(void) fprintf(wrhead, "lines = %i\n", Header::nlines); // number of lines
	(void) fprintf(wrhead, "bands = %i\n", Header::bands); // number of bands
	(void) fprintf(wrhead, "header offset = 0\n");
	(void) fprintf(wrhead, "file type = ENVI Standard\n");
//	(void) fprintf(wrhead, "data type = %i\n", dattype); // output data type
	(void) fprintf(wrhead, "data type = %i\n", 1); // output data type
	(void) fprintf(wrhead, "interleave = %s\n", Header::interleave.c_str()); // interleave format (bsq, bil, or bip)
	(void) fprintf(wrhead, "sensor type = Unknown\n");
	(void) fprintf(wrhead, "byte order = 0\n");
	(void) fprintf(wrhead, "map info = {%s, 1.00000, 1.00000, %le, %le, %le, %le, %s, %s, %s, units=%s}\n", Header::coordsys.c_str(), Header::ulx, Header::uly, Header::xres, Header::yres, Header::utm_zone_number.c_str(), Header::utm_zone_band.c_str(), Header::datum.c_str(), Header::units.c_str());
	(void) fprintf(wrhead, "coordinate system string = {PROJCS[\"UTM_Zone_14N\",GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-99.0],PARAMETER[\"Scale_Factor\",0.9996],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]}\n");
	(void) fprintf(wrhead, "data ignore value = -99999\n");
	(void) fprintf(wrhead, "wavelength units = Unknown");

	// close the header file
	fclose(wrhead);

//	cout << "Successfully wrote " << tmp.c_str() << endl;

	return true;
};

bool Header::writeHDR(string filename, vector<int> outinfo){
	string tmp = filename.append(".hdr");

	// initialize the file pointer
	FILE *wrhead;

	// open the file
	wrhead = fopen(tmp.c_str(), "w");
	if(!wrhead){
		cerr << "ERROR: Cannot write " << tmp.c_str() << endl;
		exit(1);
	}

//	dattype = datout(outinfo);

	Header::interleave = "bsq";

	// write the ascii header file
	(void) fprintf(wrhead, "ENVI\n");
	(void) fprintf(wrhead, "description = {%s}\n", filename); // file description
	(void) fprintf(wrhead, "samples = %i\n", Header::ncols); // number of columns
	(void) fprintf(wrhead, "lines = %i\n", Header::nlines); // number of lines
	(void) fprintf(wrhead, "bands = %i\n", Header::bands); // number of bands
	(void) fprintf(wrhead, "header offset = 0\n");
	(void) fprintf(wrhead, "file type = ENVI Standard\n");
//	(void) fprintf(wrhead, "data type = %i\n", dattype); // output data type
	(void) fprintf(wrhead, "data type = %i\n", 2); // output data type
	(void) fprintf(wrhead, "interleave = %s\n", Header::interleave.c_str()); // interleave format (bsq, bil, or bip)
	(void) fprintf(wrhead, "sensor type = Unknown\n");
	(void) fprintf(wrhead, "byte order = 0\n");
	(void) fprintf(wrhead, "map info = {%s, 1.00000, 1.00000, %le, %le, %le, %le, %s, %s, %s, units=%s}\n", Header::coordsys.c_str(), Header::ulx, Header::uly, Header::xres, Header::yres, Header::utm_zone_number.c_str(), Header::utm_zone_band.c_str(), Header::datum.c_str(), Header::units.c_str());
	(void) fprintf(wrhead, "coordinate system string = {PROJCS[\"UTM_Zone_14N\",GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-99.0],PARAMETER[\"Scale_Factor\",0.9996],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]}\n");
	(void) fprintf(wrhead, "data ignore value = -99999\n");
	(void) fprintf(wrhead, "wavelength units = Unknown");

	// close the header file
	fclose(wrhead);

//	cout << "Successfully wrote " << tmp.c_str() << endl;

	return true;
};

bool Header::writeHDR(string filename, vector<long int> outinfo){
	string tmp = filename.append(".hdr");

	// initialize the file pointer
	FILE *wrhead;

	// open the file
	wrhead = fopen(tmp.c_str(), "w");
	if(!wrhead){
		cerr << "ERROR: Cannot write " << tmp.c_str() << endl;
		exit(1);
	}

//	dattype = datout(outinfo);

	Header::interleave = "bsq";

	// write the ascii header file
	(void) fprintf(wrhead, "ENVI\n");
	(void) fprintf(wrhead, "description = {%s}\n", filename); // file description
	(void) fprintf(wrhead, "samples = %i\n", Header::ncols); // number of columns
	(void) fprintf(wrhead, "lines = %i\n", Header::nlines); // number of lines
	(void) fprintf(wrhead, "bands = %i\n", Header::bands); // number of bands
	(void) fprintf(wrhead, "header offset = 0\n");
	(void) fprintf(wrhead, "file type = ENVI Standard\n");
//	(void) fprintf(wrhead, "data type = %i\n", dattype); // output data type
	(void) fprintf(wrhead, "data type = %i\n", 3); // output data type
	(void) fprintf(wrhead, "interleave = %s\n", Header::interleave.c_str()); // interleave format (bsq, bil, or bip)
	(void) fprintf(wrhead, "sensor type = Unknown\n");
	(void) fprintf(wrhead, "byte order = 0\n");
	(void) fprintf(wrhead, "map info = {%s, 1.00000, 1.00000, %le, %le, %le, %le, %s, %s, %s, units=%s}\n", Header::coordsys.c_str(), Header::ulx, Header::uly, Header::xres, Header::yres, Header::utm_zone_number.c_str(), Header::utm_zone_band.c_str(), Header::datum.c_str(), Header::units.c_str());
	(void) fprintf(wrhead, "coordinate system string = {PROJCS[\"UTM_Zone_14N\",GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-99.0],PARAMETER[\"Scale_Factor\",0.9996],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]}\n");
	(void) fprintf(wrhead, "data ignore value = -99999\n");
	(void) fprintf(wrhead, "wavelength units = Unknown");

	// close the header file
	fclose(wrhead);

//	cout << "Successfully wrote " << tmp.c_str() << endl;

	return true;
};

bool Header::writeHDR(string filename, vector<float> outinfo){
	string tmp = filename.append(".hdr");

	// initialize the file pointer
	FILE *wrhead;

	// open the file
	wrhead = fopen(tmp.c_str(), "w");
	if(!wrhead){
		cerr << "ERROR: Cannot write " << tmp.c_str() << endl;
		exit(1);
	}

//	dattype = datout(outinfo);

	Header::interleave = "bsq";

	// write the ascii header file
	(void) fprintf(wrhead, "ENVI\n");
	(void) fprintf(wrhead, "description = (%s)\n", tmp.c_str()); // file description
	(void) fprintf(wrhead, "samples = %i\n", Header::ncols); // number of columns
	(void) fprintf(wrhead, "lines = %i\n", Header::nlines); // number of lines
	(void) fprintf(wrhead, "bands = %i\n", Header::bands); // number of bands
	(void) fprintf(wrhead, "header offset = 0\n");
	(void) fprintf(wrhead, "file type = ENVI Standard\n");
//	(void) fprintf(wrhead, "data type = %i\n", dattype); // output data type
	(void) fprintf(wrhead, "data type = %i\n", 4); // output data type
	(void) fprintf(wrhead, "interleave = %s\n", Header::interleave.c_str()); // interleave format (bsq, bil, or bip)
	(void) fprintf(wrhead, "sensor type = Unknown\n");
	(void) fprintf(wrhead, "byte order = 0\n");
	(void) fprintf(wrhead, "map info = {%s, 1.00000, 1.00000, %le, %le, %le, %le, %s, %s, %s, units=%s}\n", Header::coordsys.c_str(), Header::ulx, Header::uly, Header::xres, Header::yres, Header::utm_zone_number.c_str(), Header::utm_zone_band.c_str(), Header::datum.c_str(), Header::units.c_str());
	(void) fprintf(wrhead, "coordinate system string = {PROJCS[\"UTM_Zone_14N\",GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-99.0],PARAMETER[\"Scale_Factor\",0.9996],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]}\n");
	(void) fprintf(wrhead, "data ignore value = -99999\n");
	(void) fprintf(wrhead, "wavelength units = Unknown");

	// close the header file
	fclose(wrhead);

//	cout << "Successfully wrote " << tmp.c_str() << endl;

	return true;
};
bool Header::writeHDR(string filename, vector<double> outinfo){
	string tmp = filename.append(".hdr");

	// initialize the file pointer
	FILE *wrhead;

	// open the file
	wrhead = fopen(tmp.c_str(), "w");
	if(!wrhead){
		cerr << "ERROR: Cannot write " << tmp.c_str() << endl;
		exit(1);
	}

//	dattype = datout(outinfo);

	Header::interleave = "bsq";

	// write the ascii header file
	(void) fprintf(wrhead, "ENVI\n");
	(void) fprintf(wrhead, "description = ", filename, "\n"); // file description
	(void) fprintf(wrhead, "samples = %i\n", Header::ncols); // number of columns
	(void) fprintf(wrhead, "lines = %i\n", Header::nlines); // number of lines
	(void) fprintf(wrhead, "bands = %i\n", Header::bands); // number of bands
	(void) fprintf(wrhead, "header offset = 0\n");
	(void) fprintf(wrhead, "file type = ENVI Standard\n");
//	(void) fprintf(wrhead, "data type = %i\n", dattype); // output data type
	(void) fprintf(wrhead, "data type = %i\n", 5); // output data type
	(void) fprintf(wrhead, "interleave = %s\n", Header::interleave.c_str()); // interleave format (bsq, bil, or bip)
	(void) fprintf(wrhead, "sensor type = Unknown\n");
	(void) fprintf(wrhead, "byte order = 0\n");
	(void) fprintf(wrhead, "map info = {%s, 1.00000, 1.00000, %le, %le, %le, %le, %s, %s, %s, units=%s}\n", Header::coordsys.c_str(), Header::ulx, Header::uly, Header::xres, Header::yres, Header::utm_zone_number.c_str(), Header::utm_zone_band.c_str(), Header::datum.c_str(), Header::units.c_str());
	(void) fprintf(wrhead, "coordinate system string = {PROJCS[\"UTM_Zone_14N\",GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-99.0],PARAMETER[\"Scale_Factor\",0.9996],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]}\n");
	(void) fprintf(wrhead, "data ignore value = -99999\n");
	(void) fprintf(wrhead, "wavelength units = Unknown");

	// close the header file
	fclose(wrhead);

//	cout << "Successfully wrote " << tmp.c_str() << endl;

	return true;
};

bool Header::writeDAT(string fname, vector<unsigned int> outrast){
	string tmp = fname.append(".dat");

	// open the file output stream
	ofstream fout;								// initiate output stream
	fout.open(tmp, ios::out | ios::binary);		// open file from output stream
	if (!fout) {								// exit if unable to open (create) file
		cerr << "Unable to write " << tmp << endl;
		system("pause");
	}

	const char* dat = reinterpret_cast<const char*>(&outrast[0]);
	size_t bytes = outrast.size() * sizeof(unsigned int);

	// write out vector to binary file
	fout.write(dat, bytes);

	// close the file
	fout.close();

//	cout << "Successfully wrote " << tmp << endl;

	///////////////////// START DEBUGGING /////////////////////
//	cout << "writeDAT::outdat.size() = " << (outdat.size()) << endl;
//	cout << "writeDAT output file size = " << (outdat.size() * sizeof(float)) << endl;
	/////////////////////  END DEBUGGING  /////////////////////

	return true;
};

bool Header::writeDAT(string fname, vector<int> outrast){
	string tmp = fname.append(".dat");

	// open the file output stream
	ofstream fout;								// initiate output stream
	fout.open(tmp, ios::out | ios::binary);		// open file from output stream
	if (!fout) {								// exit if unable to open (create) file
		cerr << "Unable to write " << tmp << endl;
		system("pause");
	}

	const char* dat = reinterpret_cast<const char*>(&outrast[0]);
	size_t bytes = outrast.size() * sizeof(int);

	// write out vector to binary file
	fout.write(dat, bytes);

	// close the file
	fout.close();

//	cout << "Successfully wrote " << tmp << endl;

	///////////////////// START DEBUGGING /////////////////////
//	cout << "writeDAT::outdat.size() = " << (outdat.size()) << endl;
//	cout << "writeDAT output file size = " << (outdat.size() * sizeof(float)) << endl;
	/////////////////////  END DEBUGGING  /////////////////////

	return true;
};

bool Header::writeDAT(string fname, vector<long int> outrast){
	string tmp = fname.append(".dat");

	// open the file output stream
	ofstream fout;								// initiate output stream
	fout.open(tmp, ios::out | ios::binary);		// open file from output stream
	if (!fout) {								// exit if unable to open (create) file
		cerr << "Unable to write " << tmp << endl;
		system("pause");
	}

	const char* dat = reinterpret_cast<const char*>(&outrast[0]);
	size_t bytes = outrast.size() * sizeof(long int);

	// write out vector to binary file
	fout.write(dat, bytes);

	// close the file
	fout.close();

//	cout << "Successfully wrote " << tmp << endl;

	///////////////////// START DEBUGGING /////////////////////
//	cout << "writeDAT::outdat.size() = " << (outdat.size()) << endl;
//	cout << "writeDAT output file size = " << (outdat.size() * sizeof(float)) << endl;
	/////////////////////  END DEBUGGING  /////////////////////

	return true;
};

bool Header::writeDAT(string fname, vector<float> outrast){
	string tmp = fname.append(".dat");

//	cout << outrast[4141] << " FROM writeDAT in DATASTRUCT.CPP" << endl;

	// open the file output stream
	ofstream fout;								// initiate output stream
	fout.open(tmp, ios::out | ios::binary);		// open file from output stream
	if (!fout) {								// exit if unable to open (create) file
		cerr << "Unable to write " << tmp << endl;
		system("pause");
	}

	const char* dat = reinterpret_cast<const char*>(&outrast[0]);
	size_t bytes = outrast.size() * sizeof(float);

	// write out vector to binary file
	fout.write(dat, bytes);

	// close the file
	fout.close();

//	cout << "Successfully wrote " << tmp << endl;

	///////////////////// START DEBUGGING /////////////////////
//	cout << "writeDAT::outdat.size() = " << (outdat.size()) << endl;
//	cout << "writeDAT output file size = " << (outdat.size() * sizeof(float)) << endl;
	/////////////////////  END DEBUGGING  /////////////////////

	return true;
};

bool Header::writeDAT(string fname, vector<double> outrast){
	string tmp = fname.append(".dat");

	// open the file output stream
	ofstream fout;								// initiate output stream
	fout.open(tmp, ios::out | ios::binary);		// open file from output stream
	if (!fout) {								// exit if unable to open (create) file
		cerr << "Unable to write " << tmp << endl;
		system("pause");
	}

	const char* dat = reinterpret_cast<const char*>(&outrast[0]);
	size_t bytes = outrast.size() * sizeof(double);

	// write out vector to binary file
	fout.write(dat, bytes);

	// close the file
	fout.close();

//	cout << "Successfully wrote " << tmp << endl;

	///////////////////// START DEBUGGING /////////////////////
//	cout << "writeDAT::outdat.size() = " << (outdat.size()) << endl;
//	cout << "writeDAT output file size = " << (outdat.size() * sizeof(float)) << endl;
	/////////////////////  END DEBUGGING  /////////////////////

	return true;
};


///////////////////////////////////////////////////////////////
// OUTRASTER FUNCTIONS
///////////////////////////////////////////////////////////////

void OutRaster::rsize(int new_dim){
	OutRaster::x.resize(new_dim);
	OutRaster::y.resize(new_dim);
	OutRaster::val.resize(new_dim);
	OutRaster::prob.resize(new_dim);
}

// check dimensions & copy XY coordinate data
bool OutRaster::copyxy(Raster r1, Raster r2){
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size()){
		cerr << "ERROR: X and/or Y dimensions are not the same. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size() ||
				r1.ulx!=r2.ulx ||
				r1.uly!=r2.uly){
		cerr << "ERROR: Upper-left X coordinates do not match. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size() ||
				r1.ulx!=r2.ulx ||
				r1.uly!=r2.uly){
		cerr << "ERROR: Upper-left Y coordinates do not match. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
			r1.y.size()!=r2.y.size() ||
			r1.ulx!=r2.ulx ||
			r1.uly!=r2.uly){
		OutRaster::x = r1.x;
		OutRaster::y = r1.y;
	}

	return true;
}

// simple raster subtraction (no error propagation)
bool OutRaster::subtract(Raster t1, Raster t2){
	for(size_t i=0; i<OutRaster::val.size(); i++)
	{
		OutRaster::val[i] = t2.val[i] - t1.val[i];
	}

	return true;
}

// sort raster based on X & Y coordinates
bool OutRaster::subtract_epsilon(Raster t1, Raster t1e, Raster t2, Raster t2e){
	for(size_t i=0; i<OutRaster::val.size(); i++){
		if((t1.val[i] - t1e.val[i]) < (t2.val[i] + t2e.val[i]) ||
				(t1.val[i] + t1e.val[i]) > (t2.val[i] - t2e.val[i])){
			OutRaster::val[i] = -99999;
		} else{
			OutRaster::val[i] = t2.val[i] - t1.val[i];
		}
	}

	return true;
}

bool OutRaster::pchange(Raster t1, Raster t1e, Raster t2, Raster t2e, int nsimulations){
	unsigned seed = chrono::system_clock::now().time_since_epoch().count();	// random number seed value (varies with computer clock)
	default_random_engine generator(seed);;									// random number generator

	// fill rasters with default no data values
	fill(OutRaster::val.begin(), OutRaster::val.end(), -99999);
	fill(OutRaster::prob.begin(), OutRaster::prob.end(), -99999);

	int iter;

	for(size_t i=0; i<OutRaster::val.size(); i++)
	{
//		cout << "TEST A - " << i << " ::: " << t1.val[i] << " || " << t2.val[i] << endl;
//		if(t1.val[i] > -999 && t2.val[i] > -999){
//			cout << "TEST A2 - " << i << " ::: " << t1.val[i] << " || " << t2.val[i] << endl;
//		}


		// track change values
		iter = 0;
		int p_change = 0;

		// option 1: update single value
		float chng = 0;

		// option 2: vectors
//		vector<float> surf1, surf2;		// 2a: individual vectors
//		vector<float> surf_change;		// 2b: combined change vector

		for(int l=0; l<nsimulations; l++){
//			cout << "TEST B - " << i << " || " << l << " ::: " << t1.val[i] << " || " << t2.val[i] << endl;
			if(t1.val[i] > -999 && t2.val[i] > -999){
//				cout << "TEST C - " << i << " || " << l << " ::: " << t1.val[i] << " || " << t2.val[i] << endl;
				// simulate normal distribution, based on mean of 0.0 and assuming accuracy is reported as 95% confidence interval
				normal_distribution<float> dist1(0.0, (t1e.val[i]/1.96));
				normal_distribution<float> dist2(0.0, (t2e.val[i]/1.96));

				// generate random error from a normal distribution, constraining it to +- 3 standard deviations (captures 99.7%)
				float er1 = dist1(generator);
				while(!(er1 <= 3*(t1e.val[i]/1.96))){
					er1 = dist1(generator);
				}
				float er2 = dist2(generator);
				while(!(er2 <= 3*(t2e.val[i]/1.96))){
					er2 = dist2(generator);
				}

//				if(i<4000) cout << i << "(" << l << ") (" << chng << "/" << iter << ") ===> " /*<< pmr1 << " :: "*/ << er1 << " --- " /*<< pmr2 << " :: "*/ << er2 << endl;

				// option 1: update single value
				chng += (((t2.val[i] + er2) - (t1.val[i] + er1)));

//				cout << "i: " << i << "; OLD: " << p_change << "; sims: " << l << endl;
//				p_change++;
//				cout << "i: " << i << "; NEW: " << p_change << "; sims: " << l << endl;

//				cout << "i=" << i << "; change=" << chng << "; prob_counter=" << p_change << endl;

				// option 2a: individual vectors
//				surf1.push_back(t1.val[i] + er1);
//				surf2.push_back(t2.val[i] + er2);

				// option 2b: combined change vector
//				surf_change.push_back((((t2.val[i] + er2) - (t1.val[i] + er1))));

				////// UPDATE PROBABILTY VECTOR //////
				if((t1.val[i]-abs(er1) > t2.val[i]+abs(er2)) ||
						(t2.val[i]-abs(er2) > t1.val[i]+abs(er1))){
//					cout << "i: " << i << "; OLD: " << p_change << "; sims: " << l << endl;
					p_change++;
//					cout << "i: " << i << "; NEW: " << p_change << "; sims: " << l << endl;
				}
//				if(((t2.val[i] + abs(er2)) < (t1.val[i] - abs(er1))) ||
//						((t2.val[i] - abs(er2)) > (t1.val[i] + abs(er1)))){
//					// increase probability of change counter
////					cout << "i: " << i << "; OLD: " << p_change << "; sims: " << l << endl;
//					p_change++;
////					cout << "i: " << i << "; NEW: " << p_change << "; sims: " << l << endl;
//				}

				iter++;
			}
		}

		// option 2b: combined change vector
//		float chng = accumulate(surf_change.begin(), surf_change.end(), 0.0);


		////// UPDATE RASTER VALUES //////
		if(t1.val[i] > -999 && t2.val[i] > -999){
			OutRaster::val[i] = chng/iter;
		} else OutRaster::val[i] = -99999;

//		cout << "TEST PCHANGE: " << p_change/nsimulations << " __ " << i << endl;

		////// UPDATE PROBABILTY VECTOR //////
		// only update value if_change > 0
		if(p_change > 0 && t1.val[i] > -999 && t2.val[i] > -999){
			// compute change probability
			float foo = (float)p_change/(float)nsimulations;
			OutRaster::prob[i] = foo;
//			cout << "NON-ZERO: " << i << " -- " << p_change << " || " << nsimulations << " === " << OutRaster::prob[i] << endl;
		} else if(p_change == 0 && t1.val[i] > -999 && t2.val[i] > -999){
			OutRaster::prob[i] = 0;
//			cout << "NON-ZERO: " << foo << " === " << prob_change.val[i] << " __ " << i << endl;
		} else OutRaster::prob[i] = -99999;

//		if(i<4142) cout << "PCHANGE_VALS: " << i << " --- " << chng << "/" << iter << " = "  << OutRaster::val[i] <<endl;
	}

	return true;
}


///////////////////////////////////////////////////////////////
// RASTER FUNCTIONS
///////////////////////////////////////////////////////////////
//Raster::Raster();

//Raster::~Raster();

void Raster::rsize(int new_dim){
	Raster::x.resize(new_dim);
	Raster::y.resize(new_dim);
	Raster::val.resize(new_dim);
}

bool Raster::readENVIdata(string fn, Header hdr){
	register int count, t, s, idx;
	fstream f;

	// open the file
	f.open(fn, ios::binary | ios::in);
	if(!f){
		cerr << "ERROR: Cannot open " << fn << endl;
		return false;
	}

	cout << "Reading data from " << fn << "..." << endl;

	// resize raster (all vectors) to the appropriate length,
	// as defined by information in the header file
	Raster::rsize(hdr.npix);

	// copy upper left X and Y coordinates from header
	Raster::ulx = hdr.ulx;
	Raster::uly = hdr.uly;

	if(hdr.datatype == 4){
		f.read(reinterpret_cast<char*> (Raster::val.data()), Raster::val.size()*sizeof(float));
//		cout << Raster::val.size() << endl;
//		cout << sizeof(float) << endl;
//		cout << (Raster::val.size()*sizeof(float)) << endl;
		for(s=0; s<hdr.nlines; s++){
			for(t=0; t<hdr.ncols; t++){
				idx = s*hdr.ncols + t;

				Raster::x[idx] = hdr.ulx + t*hdr.xres;
				Raster::y[idx] = hdr.uly - s*hdr.yres;

				if(Raster::x[idx] > hdr.xmax){
					hdr.xmax = Raster::x[idx];
				}
				if(Raster::y[idx] < hdr.ymin){
					hdr.ymin = Raster::y[idx];
				}

				if(Raster::val[idx] > -9999){
					if(hdr.valmin > Raster::val[idx] && Raster::val[idx] > -100){
						hdr.valmin = Raster::val[idx];
					} else if(Raster::val[idx] > hdr.valmax){
						hdr.valmax = Raster::val[idx];
					}
				}
			}
		}
	}

	// print info about the file to the screen
	cout << "FILE INFORMATION:" << endl;
	cout << "Upper Left (" << hdr.ulx << ", " << hdr.uly << ")" << endl;
	cout << "Lower Right (" << hdr.xmax << ", " << hdr.ymin << ")" << endl;
	cout << "Resolution (X, Y): (" << hdr.xres << ", " << hdr.yres << ")" << endl;
	cout << "Z min & max: " << hdr.valmin << " - " << hdr.valmax << endl;
	cout << "Rows: " << hdr.nlines << ", Columns: " << hdr.ncols << ", Pixels: " << hdr.npix << "\n" << endl;

	// close the file
	f.close();

	return true;
}

// check dimensions & copy XY coordinate data
bool Raster::copyxy(Raster r1, Raster r2){
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size()){
		cerr << "ERROR: X and/or Y dimensions are not the same. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size() ||
				r1.ulx!=r2.ulx ||
				r1.uly!=r2.uly){
		cerr << "ERROR: Upper-left X coordinates do not match. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
				r1.y.size()!=r2.y.size() ||
				r1.ulx!=r2.ulx ||
				r1.uly!=r2.uly){
		cerr << "ERROR: Upper-left Y coordinates do not match. Unable to copy to output raster." << endl;

		return false;
	}
	if(r1.x.size()!=r2.x.size() ||
			r1.y.size()!=r2.y.size() ||
			r1.ulx!=r2.ulx ||
			r1.uly!=r2.uly){
		Raster::x = r1.x;
		Raster::y = r1.y;
	}

	return true;
}

// simple raster subtraction (no error propagation)
bool Raster::subtract(Raster t1, Raster t2){
	for(size_t i=0; i<Raster::val.size(); i++)
	{
		Raster::val[i] = t2.val[i] - t1.val[i];
	}

	return true;
}

// sort raster based on X & Y coordinates
bool Raster::subtract_epsilon(Raster t1, Raster t1e, Raster t2, Raster t2e){
	for(size_t i=0; i<Raster::val.size(); i++){
		if((t1.val[i] - t1e.val[i]) < (t2.val[i] + t2e.val[i]) ||
				(t1.val[i] + t1e.val[i]) > (t2.val[i] - t2e.val[i])){
			Raster::val[i] = -99999;
		} else{
			Raster::val[i] = t2.val[i] - t1.val[i];
		}
	}

	return true;
}

//bool Raster::pchange(Raster t1, Raster t1e, Raster t2, Raster t2e, int nsimulations){
//	unsigned seed = chrono::system_clock::now().time_since_epoch().count();
//	default_random_engine generator(seed);
//
//	// fill probability raster with default no data values
//	fill(Raster::val.begin(), Raster::val.end(), -99999);
//
////	prob.val[100100] = 3745;
//	for(size_t i=0; i<Raster::val.size(); i++)
//	{
//		// compute change from t1 to t2
////		orast.val[i] = t1.val[i] - t2.val[i];
//
//		// track change values
//		int p_change = 0;
//
//		if(!((t1.val[i] - 3*t1e.val[i]) > (t2.val[i] + 3*t2.val[i])) ||
//				!((t2.val[i] - 3*t2e.val[i]) > (t1.val[i] + 3*t1e.val[i]))){
//			for(int l=0; l<nsimulations; l++){
//
//				// only simulate change if both raster values are non-null
//				if(t1.val[i] > -999 && t2.val[i] > -999){
//					// simulate normal distribution, based on mean of 0.0 and assuming accuracy is reported as 95% confidence interval
//					normal_distribution<float> dist1(0.0, (t1e.val[i]/1.96));
//					normal_distribution<float> dist2(0.0, (t2e.val[i]/1.96));
//
//					// generate random error from a normal distribution, constraining it to +- 3 standard deviations (captures 99.7%)
//					float er1 = dist1(generator);
//					while(!(er1 <= 3*(t1e.val[i]/1.96))){
//						er1 = dist1(generator);
//					}
//					float er2 = dist2(generator);
//					while(!(er2 <= 3*(t2e.val[i]/1.96))){
//						er2 = dist2(generator);
//					}
//	//				cout << t1e.val[i] << " --- " << t2e.val[i] << " ||| " << (t1e.val[i]/1.96) << " ::" << (t1e.val[i]/1.96) << " ==> " << er1 << " ::: " << er2 << endl;
//
//					if(((t2.val[i] + abs(er2)) < (t1.val[i] - abs(er1))) ||
//							((t2.val[i] - abs(er2)) > (t1.val[i] + abs(er1)))){
//						// increase probability of change counter
//	//					cout << "i: " << i << "; OLD: " << p_change << "; sims: " << l << endl;
//						p_change++;
//	//					cout << "i: " << i << "; NEW: " << p_change << "; sims: " << l << endl;
//					}
//				}
//			}
//		}
//
//
//
//
//		// only update value if_change > 0
//		if(p_change > 0 && t1.val[i] > -999 && t2.val[i] > -999){
//			// compute change probability
//			float foo = (float)p_change/(float)nsimulations;
//			Raster::val[i] = foo;
////			cout << "NON-ZERO: " << foo << " === " << prob.val[i] << " __ " << i << endl;
//		} else if(p_change == 0 && t1.val[i] > -999 && t2.val[i] > -999){
//			Raster::val[i] = 0;
////			cout << "NON-ZERO: " << foo << " === " << prob.val[i] << " __ " << i << endl;
//		} else Raster::val[i] = -99999;
//
////		if(i<4142) cout << "PCHANGE: " << i << " --- " << Raster::val[i] <<endl;
//	}
//
//	return true;
//}

//bool Raster::pchange_vals(Raster t1, Raster t1e, Raster t2, Raster t2e, int nsimulations){
//	unsigned seed = chrono::system_clock::now().time_since_epoch().count();
//	default_random_engine generator(seed);;
//
//	// fill probability raster with default no data values
//	fill(Raster::val.begin(), Raster::val.end(), -99999);
//
//	int iter;
//
//	for(size_t i=0; i<Raster::val.size(); i++)
//	{
//		// track change values
//		iter = 0;
//
//		// there are several
//
//		// option 1: update single value
//		float chng = 0;
//
//		// option 2: vectors
////		vector<float> surf1, surf2;		// 2a: individual vectors
////		vector<float> surf_change;		// 2b: combined change vector
//
//		for(int l=0; l<nsimulations; l++){
//			if(t1.val[i] > -999 && t2.val[i] > -999){
//				// simulate normal distribution, based on mean of 0.0 and assuming accuracy is reported as 95% confidence interval
//				normal_distribution<float> dist1(0.0, (t1e.val[i]/1.96));
//				normal_distribution<float> dist2(0.0, (t2e.val[i]/1.96));
//
//				// generate random error from a normal distribution, constraining it to +- 3 standard deviations (captures 99.7%)
//				float er1 = dist1(generator);
//				while(!(er1 <= 3*(t1e.val[i]/1.96))){
//					er1 = dist1(generator);
//				}
//				float er2 = dist2(generator);
//				while(!(er2 <= 3*(t2e.val[i]/1.96))){
//					er2 = dist2(generator);
//				}
//
////				if(i<4000) cout << i << "(" << l << ") (" << chng << "/" << iter << ") ===> " /*<< pmr1 << " :: "*/ << er1 << " --- " /*<< pmr2 << " :: "*/ << er2 << endl;
//
//				// option 1: update single value
//				chng += (((t2.val[i] + er2) - (t1.val[i] + er1)));
//
//				// option 2a: individual vectors
////				surf1.push_back(t1.val[i] + er1);
////				surf2.push_back(t2.val[i] + er2);
//
//				// option 2b: combined change vector
////				surf_change.push_back((((t2.val[i] + er2) - (t1.val[i] + er1))));
//
//				iter++;
//			}
//		}
//
//		// option 2b: combined change vector
////		float chng = accumulate(surf_change.begin(), surf_change.end(), 0.0);
//
//		////// UPDATE RASTER VALUES //////
//		if(t1.val[i] > -999 && t2.val[i] > -999){
//			Raster::val[i] = chng/iter;
//		} else Raster::val[i] = -99999;
//	}
//
//	return true;
//}

/*
unsigned seed = chrono::system_clock::now().time_since_epoch().count();

default_random_engine generator(seed);
normal_distribution<float> dist1(0.0, (0.15/1.96));
normal_distribution<float> dist2(0.0, 0.15);

for(int i=0; i<11; i++){
	float er2 = dist2(generator);
	float er1 = dist1(generator);
	cout << er1 << " ::: " << er2 << endl;
}
*/
