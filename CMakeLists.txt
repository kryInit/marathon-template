cmake_minimum_required(VERSION 3.16)
project(marathon)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_COMPILER gcc)
set(CMAKE_CXX_COMPILER g++)

set(CMAKE_CXX_FLAGS "-O2 -Wall")

add_executable(solver main.cpp)
