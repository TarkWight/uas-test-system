#cmake/Resources.cmake

function(deploy_runtime_assets TARGET_NAME)
    set(ASSETS
        "${PROJECT_SOURCE_DIR}/config/report.toml"
        "${PROJECT_SOURCE_DIR}/config/uav.example.toml"
        "${PROJECT_SOURCE_DIR}/config/telemetry.toml"
    )

    if(APPLE)
        foreach(ASSET IN LISTS ASSETS)
            set_source_files_properties(
                "${ASSET}"
                PROPERTIES
                    MACOSX_PACKAGE_LOCATION "Resources"
            )
        endforeach()

        target_sources(
            ${TARGET_NAME}
            PRIVATE
                ${ASSETS}
        )
    else()
        add_custom_command(
            TARGET ${TARGET_NAME}
            POST_BUILD

            COMMAND
                ${CMAKE_COMMAND} -E make_directory
                "$<TARGET_FILE_DIR:${TARGET_NAME}>/config"

            COMMAND
                ${CMAKE_COMMAND} -E copy_if_different
                ${ASSETS}
                "$<TARGET_FILE_DIR:${TARGET_NAME}>/config"

            COMMENT
                "Deploying runtime config"

            VERBATIM
        )
    endif()
endfunction()
