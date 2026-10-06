#include "strata/prefill/dg_tail.hpp"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>

struct Case { int type, experts; int64_t maximum, total; bool selected; };

int main() {
    setenv("STRATA_DEEPGEMM_TAIL", "1", 1);
    strata::prefill::dg_tail::Context enabled;
    const Case cases[] = {
        {8,4,1156,1464,true}, {8,4,1170,3107,false},
        {8,2,128,256,false}, {7,4,1156,1464,false},
        {8,4,511,600,false}, {8,4,1537,1600,false},
        {8,4,1200,1600,true}, {8,4,1200,1601,false},
        {8,4,1102,1167,false}, {8,4,1397,1548,false},
        {8,4,646,667,true}, {8,4,1200,1333,false},
        {8,4,1200,1334,true}, {8,4,1200,std::numeric_limits<int64_t>::max(),false},
        {8,4,-1,1,false}, {8,4,512,-1,false}, {8,4,512,511,false},
        {8,4,512,2049,false}, {8,4,1536,2048,true},
        {8,4,1024,1137,false}, {8,4,1024,1138,true},
        {8,4,1023,1023,true}, {8,4,1024,1024,false},
    };
    for (const auto& c : cases) {
        if (enabled.selected(c.type,c.experts,c.maximum,c.total) != c.selected)
            throw std::runtime_error("dispatch boundary mismatch");
    }
    int32_t invalid[4] = {1,1,1,6145};
    float dummy = 0;
    if (enabled.run(&dummy,&dummy,invalid,&dummy,nullptr))
        throw std::runtime_error("accepted an over-capacity count");
    invalid[3] = -1;
    if (enabled.run(&dummy,&dummy,invalid,&dummy,nullptr))
        throw std::runtime_error("accepted a negative count");
    if (enabled.run(nullptr,&dummy,invalid,&dummy,nullptr))
        throw std::runtime_error("accepted a null input");
    setenv("STRATA_DEEPGEMM_TAIL", "0", 1);
    setenv("STRATA_DEEPGEMM_TAIL_RESERVE", "0", 1);
    strata::prefill::dg_tail::Context disabled;
    if (disabled.ready() || disabled.selected(8,4,1156,1464))
        throw std::runtime_error("default-off path allocates or selects adapter");
    std::printf("PASS %zu dispatch boundaries, invalid inputs and disabled construction\n",
                sizeof(cases)/sizeof(cases[0]));
}
