#include <Domain/Common/Time.hpp>

namespace domain {

namespace {

constexpr Seconds minRequiredDuration{1};
constexpr Seconds maxDuration = std::chrono::hours{24};

} // namespace

TestDurationCreationResult TestDuration::required(Seconds requested) noexcept {
    if (requested < minRequiredDuration) {
        return {
            TestDuration{minRequiredDuration},
            TimeAdjustment{
                .requested = requested,
                .applied = minRequiredDuration,
                .reason = TimeAdjustmentReason::BelowMinimum,
            },
        };
    }

    if (requested > maxDuration) {
        return {
            TestDuration{maxDuration},
            TimeAdjustment{
                .requested = requested,
                .applied = maxDuration,
                .reason = TimeAdjustmentReason::AboveMaximum,
            },
        };
    }

    return {
        TestDuration{requested},
        std::nullopt,
    };
}

TestDurationCreationResult TestDuration::optional(Seconds requested) noexcept {
    constexpr Seconds minimum{0};

    if (requested < minimum) {
        return {
            TestDuration{minimum},
            TimeAdjustment{
                .requested = requested,
                .applied = minimum,
                .reason = TimeAdjustmentReason::NegativeValue,
            },
        };
    }

    if (requested > maxDuration) {
        return {
            TestDuration{maxDuration},
            TimeAdjustment{
                .requested = requested,
                .applied = maxDuration,
                .reason = TimeAdjustmentReason::AboveMaximum,
            },
        };
    }

    return {
        TestDuration{requested},
        std::nullopt,
    };
}

TestDuration::TestDuration(Seconds value) noexcept : value_(value) {
}

Seconds TestDuration::value() const noexcept {
    return value_;
}

ElapsedTimeCreationResult ElapsedTime::from(Seconds requested) noexcept {
    constexpr Seconds minimum{0};

    if (requested < minimum) {
        return {
            ElapsedTime{minimum},
            TimeAdjustment{
                .requested = requested,
                .applied = minimum,
                .reason = TimeAdjustmentReason::NegativeValue,
            },
        };
    }

    return {
        ElapsedTime{requested},
        std::nullopt,
    };
}

ElapsedTime::ElapsedTime(Seconds value) noexcept : value_(value) {
}

Seconds ElapsedTime::value() const noexcept {
    return value_;
}

RemainingTimeCreationResult RemainingTime::from(Seconds requested) noexcept {
    constexpr Seconds minimum{0};

    if (requested < minimum) {
        return {
            RemainingTime{minimum},
            TimeAdjustment{
                .requested = requested,
                .applied = minimum,
                .reason = TimeAdjustmentReason::NegativeValue,
            },
        };
    }

    return {
        RemainingTime{requested},
        std::nullopt,
    };
}

RemainingTime::RemainingTime(Seconds value) noexcept : value_(value) {
}

Seconds RemainingTime::value() const noexcept {
    return value_;
}

} // namespace domain