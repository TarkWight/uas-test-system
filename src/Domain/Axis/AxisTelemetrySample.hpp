#pragma once

#include <Domain/Axis/AxisId.hpp>

#include <chrono>

namespace domain {

using TelemetrySessionTime = std::chrono::milliseconds;

/*
 * Представляет валидный образец телеметрии после нормализации времени.
 */

struct AxisTelemetrySample final {
    AxisId axisId;
    TelemetrySessionTime sessionTime;

    float position;
    float setPosition;

    float torque;
    float setTorque;

    float voltage;
    float current;
};

} // namespace domain