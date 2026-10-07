cmake_minimum_required(VERSION 3.13)
# Use an existing SDK checkout. No SDK download occurs during configuration.
if(NOT PICO_SDK_PATH AND DEFINED ENV{PICO_SDK_PATH})
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
endif()
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
if(NOT PICO_SDK_PATH)
    message(FATAL_ERROR "Set PICO_SDK_PATH to your Pico SDK checkout")
endif()
project(preciousMetalProbe C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()
add_executable(${PROJECT_NAME} main.c)
set_target_properties(${PROJECT_NAME} PROPERTIES LINKER_LANGUAGE C)
pico_generate_pio_header(${PROJECT_NAME} ${CMAKE_CURRENT_LIST_DIR}/excite.pio)
target_link_libraries(${PROJECT_NAME} pico_stdlib pico_stdio_usb
    hardware_adc hardware_dma hardware_pio hardware_clocks hardware_sync)
target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Werror)
pico_enable_stdio_usb(${PROJECT_NAME} 1)
pico_enable_stdio_uart(${PROJECT_NAME} 0)
target_compile_definitions(${PROJECT_NAME} PRIVATE PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE=0)
pico_add_extra_outputs(${PROJECT_NAME})
if(PICO_NO_PICOTOOL)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/../host/bin_to_uf2.py
            ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin
            ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.uf2
        COMMENT "Generating RP2040 UF2 without picotool")
endif()
