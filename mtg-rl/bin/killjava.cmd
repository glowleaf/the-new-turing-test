@echo off
rem Kill every java.exe left over from harness runs (stray JVMs keep HDF5 files locked).
taskkill /F /IM java.exe
