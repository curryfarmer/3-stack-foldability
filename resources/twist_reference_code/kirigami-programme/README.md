# kirigami-programme
This programme takes user-defined geometries as input and generates rigidly foldable kirigami patterns into two compact stacks. It is a MATLAB application designed for analyzing and visualizing the parity of foldable structures. It integrates Python for advanced computational features to provide comprehensive analysis capabilities.

The programme was co-developed by Hetheshvar Ramasamy Rajkumar and Jingyi Yang.
To cite:
1. Yang, J., You, Z., and Rosen, D.W., Folding a tessellated uniform-thick plate into compact stacks, Proc R Soc A Math Phys Eng Sci, 2025, https://doi.org/10.1098/rspa.2025.0696
2. Rajkumar, H.R., Yang, J., You, Z., and Rosen, D.W., Supplementary Material for _Folding a tessellated uniform-thick plate into compact stacks._ 


## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Troubleshooting](#troubleshooting)
- [Support](#support)

## System Requirements

- **MATLAB**: R2021a or later
- **Python**: Version 3.10–3.12 (required for computational features)
- **Operating System**: Windows, macOS, or Linux

## Installation

### Step 1: Install the Kirigami App Toolbox

* Install the Kirigami App Toolbox
* Obtain the KirigamiApp.mltbx file.
* Double-click the .mltbx file, or, in MATLAB, go to the Home tab, click Add-Ons > Install from File, and select the toolbox file.
* MATLAB will install the app and add it to your Apps tab.

### Step 2: Install Python

1. Download the appropriate Python installer from [python.org/downloads](https://www.python.org/downloads/)
2. Select a Python version between 3.10 and 3.12
3. Run the installer
4. **Important**: Ensure the option to **"Add Python to PATH"** is selected during installation

### Step 3: Install Python Dependencies

1. Open your file explorer and navigate to the folder containing `requirements.txt`
2. Copy the folder path from the address bar
3. Open a command prompt (Windows) or terminal (macOS/Linux)
4. Change to the directory containing the requirements file:
   ```bash
   cd path/to/your/KirigamiApp/release
   ```
   Replace `path/to/your/KirigamiApp/release` with the actual path you copied

5. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

### Step 4: Verify Python Integration in MATLAB

1. Start MATLAB
2. In the Command Window, type:
   ```matlab
   pyenv
   ```
3. Verify that MATLAB displays:
   - Python version (should be 3.10–3.12)
   - Path to the Python executable
   - Status (Loaded/NotLoaded)
   - Execution mode

4. If Python is not detected (Version field appears empty):
   - Ensure Python is properly installed
   - Verify that Python is added to your system PATH variable
   - Restart MATLAB and try again

### Step 5: Launch the Kirigami App

1. Restart MATLAB after completing the installation
2. Navigate to the **Apps** tab in MATLAB
3. Locate the **Kirigami App** in the applications list
4. Click to launch the application


## Troubleshooting

### Common Issues

**Python Not Detected by MATLAB**
- Verify Python installation and PATH configuration
- Ensure Python version is between 3.10 and 3.12
- Try restarting MATLAB after Python installation

**Package Installation Errors**
- Ensure you have administrative privileges
- Try updating pip: `python -m pip install --upgrade pip`
- Use `pip install --user -r requirements.txt` if permissions are restricted

**App Not Appearing in MATLAB Apps Tab**
- Restart MATLAB completely
- Check that the app installation was successful
- Verify MATLAB version compatibility (R2021a or later required)

## Support

For additional support or questions:
- Check the troubleshooting section above
- Verify system requirements are met
- Ensure all installation steps were completed correctly

---

**Version**: 1.0  
**Last Updated**: July 2025  
**Compatible MATLAB Versions**: R2021a and later
