# DEM change probability in context of spatially variable uncertainty

This repository and the compiled program is the focus of the following paper:

> Wernette, P., J. Lehner, and C. Houser. (2020) What change is ‘real’? A probabilistic approach to accounting for uncertainty in environmental change analysis. *Geomorphology*, 355, 107083. http://doi.org/10.1016/j.geomorph.2020.107083.

# Installation
If you are satisfied using the pre-compiled program, feel free to use the programs in the *HREF* folder. Otherwise, you will need to compile the program yourself via the following instructions.

## Dependencies
This program requires gcc/g++ be installed for compiling the C++ code into a working program. It is **highly recommended** that you compile the program in WSL2/Linux because it has `boost` support and should already have `g++` installed.

If you plan on compiling the program for Windows OS via WSL2/Linux, make sure that you have the mingw compiler installed:
```
sudo apt install mingw-w64
```

## Compiling the program
This program can be compiled using either a Windows or WSL2/Linux OS with either of the following commands. The result will be a cross-OS compatible stand-alone program.

If compiling via WSL2/Linux and only used in Linux/Unix systems:
```
g++ -lm -O2 -static *.cpp -o foo
```

If compiling via WSL2/Linux but interested in using it in a Windows system:
```
x86_64-w64-mingw32-g++ -lm -O2 -static *.cpp -o foo.exe
```

# Usage
## Data format/prep
Before using the program, please be sure that your raster files are

## Initialization file
The program requires a `params.ini` file be in the same directory as the program and ENVI format rasters. This file is a human-readable text file with the following structure:
```
input1 input_raster_name_at_t0
error1 error_raster_name_at_t0
input2 input_raster_name_at_t1
error2 error_raster_name_at_t1
oput output_raster_name
nsimulations 100
```

Where:
 - `input1` is the surface model at time 0
 - `error1` is the error surface associated with `input1` (may be spatially-variable or a constant value)
 - `input2` is the surface model at time 1
 - `error2` is the error surface associated with `input2` (may be spatially-variable or a constant value)
 - `oput` is the name of the output raster files (1: t1-t0 raster, 2: probability of real change)
 - `nsimulations` is an integer specifying how many simulations should be performed

 Larger number of simulations will take longer but will also provide a much better representation of the probability that a given pixel change is 'real.'

<details>
<summary>Example used to produce data in the associated <i>Geomorphology</i> publication</summary>
```
input1 PAIS_2016_resampled
error1 PAIS_2016_error
input2 PAIS_2017oct
error2 PAIS_2017oct_error
oput change_2016_2017oct
nsimulations 100
```
</details>

Although the described approach was initially used to describe changes in landscape elevation, the approach is adaptable to a wide range of spatially-contingent phenomenon.

The project is part of a broader collaboration to better understand landscape change and morphodynamic processes.

For questions related to this program, please contact:

Phil Wernette [pwernette@usgs.gov]()