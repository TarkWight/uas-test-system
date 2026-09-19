add_subdirectory(Domain)

qt_add_executable(uas-test-system
    main.cpp
)

target_link_libraries(uas-test-system
    PRIVATE
        uas_domain
)

deploy_runtime_assets(uas-test-system)

if(APPLE)
    set_target_properties(uas-test-system PROPERTIES
        MACOSX_BUNDLE TRUE
    )
endif()