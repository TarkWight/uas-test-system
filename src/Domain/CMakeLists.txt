add_library(uas_domain STATIC)

target_sources(uas_domain
    PRIVATE
        Common/Id.hpp
        Common/Time.hpp
)

target_include_directories(uas_domain
    PUBLIC
        ${PROJECT_SOURCE_DIR}/src
)

enable_code_quality(uas_domain)