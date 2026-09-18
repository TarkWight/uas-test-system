qt_add_executable(uas-test-system
    main.cpp
)

deploy_runtime_assets(uas-test-system)

if(APPLE)
    set_target_properties(uas-test-system PROPERTIES
        MACOSX_BUNDLE TRUE
    )
endif()