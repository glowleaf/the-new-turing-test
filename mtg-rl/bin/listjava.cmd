@echo off
rem List running java.exe processes (image name + PID) so we can kill the strays.
tasklist /FI "IMAGENAME eq java.exe" /FO CSV /NH
