#pragma once

#include <chrono>
#include <optional>

namespace domain {

using Seconds = std::chrono::seconds;

enum class TimeAdjustmentReason { BelowMinimum, AboveMaximum, NegativeValue };

struct TimeAdjustment final {
    Seconds requested;
    Seconds applied;
    TimeAdjustmentReason reason;
};

struct TestDurationCreationResult;
struct ElapsedTimeCreationResult;
struct RemainingTimeCreationResult;

class TestDuration final {
  public:
    [[nodiscard]] static TestDurationCreationResult required(Seconds requested) noexcept;
    [[nodiscard]] static TestDurationCreationResult optional(Seconds requested) noexcept;

    [[nodiscard]] Seconds value() const noexcept;

  private:
    explicit TestDuration(Seconds value) noexcept;

    Seconds value_;
};

struct TestDurationCreationResult final {
    TestDuration value;
    std::optional<TimeAdjustment> adjustment;
};

class ElapsedTime final {
  public:
    [[nodiscard]] static ElapsedTimeCreationResult from(Seconds requested) noexcept;

    [[nodiscard]] Seconds value() const noexcept;

  private:
    explicit ElapsedTime(Seconds value) noexcept;

    Seconds value_;
};

struct ElapsedTimeCreationResult final {
    ElapsedTime value;
    std::optional<TimeAdjustment> adjustment;
};

class RemainingTime final {
  public:
    [[nodiscard]] static RemainingTimeCreationResult from(Seconds requested) noexcept;

    [[nodiscard]] Seconds value() const noexcept;

  private:
    explicit RemainingTime(Seconds value) noexcept;

    Seconds value_;
};

struct RemainingTimeCreationResult final {
    RemainingTime value;
    std::optional<TimeAdjustment> adjustment;
};

} // namespace domain