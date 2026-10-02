cmake_minimum_required(VERSION 3.20)
project(OpenRecompSDL3Host VERSION 0.1.0 LANGUAGES C)

# Optional, independent integration. The OpenRecomp core does not require SDL3.
find_package(SDL3 3.2 REQUIRED CONFIG COMPONENTS SDL3)
add_library(openrecomp_sdl3_host STATIC openrecomp_sdl3_host.c)
target_compile_features(openrecomp_sdl3_host PUBLIC c_std_11)
target_include_directories(openrecomp_sdl3_host PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(openrecomp_sdl3_host PUBLIC SDL3::SDL3)

add_executable(openrecomp_sdl3_smoke demo_main.c)
target_link_libraries(openrecomp_sdl3_smoke PRIVATE openrecomp_sdl3_host)

include(CTest)
if(BUILD_TESTING)
    add_test(NAME sdl3_invalid_input
             COMMAND openrecomp_sdl3_smoke --test-invalid)
    # Only opt into the dummy-video lifecycle test on Linux; other systems
    # can run --smoke interactively or in a configured display environment.
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_test(NAME sdl3_dummy_lifecycle
                 COMMAND openrecomp_sdl3_smoke --smoke)
        set_tests_properties(sdl3_dummy_lifecycle PROPERTIES
                             ENVIRONMENT "SDL_VIDEODRIVER=dummy")
    endif()
endif()
