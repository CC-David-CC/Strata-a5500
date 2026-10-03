#pragma once

// One build-time bound for verifier, drafter and expert-work tables.
// Eight preserves the release configuration. Twenty-four is experimental.
#ifndef STRATA_VERIFY_MAX_T
#define STRATA_VERIFY_MAX_T 8
#endif
static_assert(STRATA_VERIFY_MAX_T == 8 || STRATA_VERIFY_MAX_T == 24,
              "STRATA_VERIFY_MAX_T must be 8 or experimental 24");
namespace strata {
inline constexpr int kSpecMaxT = STRATA_VERIFY_MAX_T;
inline constexpr int kSpecMaxEntries = kSpecMaxT == 8 ? 128 : 256;
static_assert(kSpecMaxT * 10 <= kSpecMaxEntries);
}
