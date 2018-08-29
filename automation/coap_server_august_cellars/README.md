From Jim Shaad

For the server:

Repository:  https://github.com/Com-AugustCellars/TestServer
Docker image: mono:latest

Commands to build server

mono nuget.exe restore TestServer.Net462.sln
msbuild /p:Configuration=Debug TestServer.Net462.sln

to run server

mono bin/debug/TestServer.exe

The server will then run until a character is pressed on the command window.
This is a terminal application and not a GUI application.

---



TestServer.exe --ipaddress=127.0.0.1 --interop-test=CoapCore

This will limit the set of resources to those that are needed by the CoAP Core test suite, although not all of the methods are implemented given that I just used the list at the top and did not look at all of the test cases until I started doing client testing this morning.

Jim
