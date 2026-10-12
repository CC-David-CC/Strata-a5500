#pragma once
#include "strata/core/verify.hpp"
#include <string>
#include <vector>
namespace strata::core {
// One fresh process, one complete forced history. No checkpoint, branch handle,
// store, stdin command protocol or state-import parameter.
int fresh_driver(const WeightTable&, const ModelGeometry&, SessionState&, const VerifyHits&,
                 const NativeHead*, PoolMultiFn, void*, bool& pool_failed,
                 const std::vector<int64_t>& tokens, const std::string& logits_path);
}
