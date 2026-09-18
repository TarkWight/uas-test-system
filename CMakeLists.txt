cmake_minimum_required(VERSION 4.2.1)

project(
    "UAS Test Stand"
    VERSION 0.1.0
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

list(APPEND CMAKE_MODULE_PATH
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake"
)

option(ENABLE_CLANG_TIDY "Enable clang-tidy" ON)
option(ENABLE_CLANG_FORMAT_CHECK "Enable clang-format check" ON)

set(CLANG_TIDY_PATH "" CACHE FILEPATH "Path to clang-tidy executable")
set(CLANG_FORMAT_PATH "" CACHE FILEPATH "Path to clang-format executable")

include(Dependencies)
include(CodeQuality)
include(Resources)

add_subdirectory(src)

