function(enable_code_quality TARGET_NAME)
    if(NOT TARGET ${TARGET_NAME})
        message(FATAL_ERROR
            "enable_code_quality(): target '${TARGET_NAME}' does not exist"
        )
    endif()

    get_target_property(_target_type ${TARGET_NAME} TYPE)

    # INTERFACE-библиотеки требуют INTERFACE scope,
    # обычные библиотеки/executable — PRIVATE.
    if(_target_type STREQUAL "INTERFACE_LIBRARY")
        set(_scope INTERFACE)
    else()
        set(_scope PRIVATE)
    endif()

    # Compiler warnings
    target_compile_options(${TARGET_NAME} ${_scope}
        $<$<CXX_COMPILER_ID:Clang,GNU>:-Wall;-Wextra;-Wpedantic;-Werror>
        $<$<CXX_COMPILER_ID:MSVC>:/W4;/WX>
    )

    # clang-tidy
    if(ENABLE_CLANG_TIDY)
        if(NOT CLANG_TIDY_PATH)
            message(FATAL_ERROR
                "ENABLE_CLANG_TIDY is ON, but CLANG_TIDY_PATH is not set"
            )
        endif()

        # INTERFACE target сам ничего не компилирует,
        # поэтому запускать clang-tidy для него бессмысленно.
        if(NOT _target_type STREQUAL "INTERFACE_LIBRARY")
            set_target_properties(${TARGET_NAME} PROPERTIES
                CXX_CLANG_TIDY "${CLANG_TIDY_PATH}"
            )
        endif()
    endif()

    # clang-format
    if(ENABLE_CLANG_FORMAT_CHECK)
        if(NOT CLANG_FORMAT_PATH)
            message(FATAL_ERROR
                "ENABLE_CLANG_FORMAT_CHECK is ON, but CLANG_FORMAT_PATH is not set"
            )
        endif()

        get_target_property(_srcs ${TARGET_NAME} SOURCES)

        if(_srcs)
            set(_fmt_files "")

            foreach(f IN LISTS _srcs)
                if(IS_ABSOLUTE "${f}")
                    set(_abs "${f}")
                else()
                    set(_abs "${CMAKE_CURRENT_SOURCE_DIR}/${f}")
                endif()

                if(_abs MATCHES "\\.(c|cc|cpp|cxx|h|hh|hpp|hxx)$")
                    list(APPEND _fmt_files "${_abs}")
                endif()
            endforeach()

            if(_fmt_files)
                add_custom_target(${TARGET_NAME}-format-check
                    COMMAND
                        "${CLANG_FORMAT_PATH}"
                        --dry-run
                        --Werror
                        ${_fmt_files}
                    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                    COMMENT "Checking ${TARGET_NAME} formatting with clang-format"
                    VERBATIM
                )

                if(NOT _target_type STREQUAL "INTERFACE_LIBRARY")
                    add_dependencies(
                        ${TARGET_NAME}
                        ${TARGET_NAME}-format-check
                    )
                endif()
            endif()
        endif()
    endif()
endfunction()
