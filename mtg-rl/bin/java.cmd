@echo off
rem java shim for the MageZero runner: xmage\mz-xmage.bat calls bare `java`, and there is
rem no system-wide JDK on this machine. Points at the Temurin 21 downloaded for this project.
"C:\Users\alpha\machinegeorge\mtg-laya\jdk\jdk-21.0.12.1+1\bin\java.exe" %*
