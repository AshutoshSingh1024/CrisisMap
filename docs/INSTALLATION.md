# Offline installation

## Prepare once on a connected machine

1. Install 64-bit Python 3.13.x.
2. Download the PySide6 dependency and its wheels into a portable folder:

   ```powershell
   py -3.13 -m pip download --dest wheels -r requirements.txt
   ```

3. Copy the entire CrisisMap folder and `wheels` folder to the offline Windows 11 computer.

## Install on the offline computer

From PowerShell in the CrisisMap folder:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --no-index --find-links .\wheels -r requirements.txt
python run.py
```

No firewall rule, server, database, token, or network configuration is needed. Do not delete the `src/crisismap/resources/data` directory; it contains the built-in offline demo map.
