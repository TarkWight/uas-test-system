#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>

namespace domain {

template <typename Tag> class Id final {
  public:
    using ValueType = std::uint32_t;

    explicit constexpr Id(ValueType value) noexcept : value_(value) {
    }

    [[nodiscard]] constexpr ValueType value() const noexcept {
        return value_;
    }

    friend constexpr bool operator==(const Id &, const Id &) = default;

  private:
    ValueType value_{};
};

template <typename Tag> struct IdHash {
    [[nodiscard]] std::size_t operator()(const Id<Tag> &id) const noexcept {
        return std::hash<typename Id<Tag>::ValueType>{}(id.value());
    }
};

} // namespace domain
