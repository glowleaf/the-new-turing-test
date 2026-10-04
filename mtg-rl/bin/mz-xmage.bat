@echo off
cd /d "%~dp0"
rem Resolve the JVM explicitly: this machine has no system-wide `java`, and the MageZero
rem runner launches this batch file with `cmd /c`, which does not inherit a shell-exported
rem PATH. JAVA_EXE can override; otherwise the project-local Temurin 21 is used.
if not defined JAVA_EXE set "JAVA_EXE=C:\Users\alpha\machinegeorge\mtg-laya\jdk\jdk-21.0.12.1+1\bin\java.exe"
rem Heap trimmed from the shipped -Xmx24g: two opponent JVMs run concurrently on a 63.7 GB
rem box, and 24 GB each plus the inference server was too close to the ceiling.
"%JAVA_EXE%" -Dlog.file=magezero.log -Derrors.file=magezeroErrors.log -Dlog4j.configuration=file:log4j.properties -Xms2g -Xmx8g -XX:+UseZGC --add-opens=java.base/java.lang=ALL-UNNAMED -jar lib\mage-magezero-1.4.58.jar %*
