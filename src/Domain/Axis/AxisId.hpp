#pragma once

#include <Domain/Common/Id.hpp>

namespace domain {

struct AxisIdTag {};

using AxisId = Id<AxisIdTag>;

inline constexpr AxisId axis0{0};
inline constexpr AxisId axis1{1};

} // namespace domain