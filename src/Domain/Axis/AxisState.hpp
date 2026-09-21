#pragma once

namespace domain {

enum class AxisState {
    Disconnected,
    Connected,
    Operating,
    Stopped,
    Error,
};

} // namespace domain