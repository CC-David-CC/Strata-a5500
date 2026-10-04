#include "strata/core/serial_worker.hpp"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <vector>

int main() {
    // Repeated non-atomic buffers test the completion publication contract.
    std::vector<unsigned> data(8192);
    int initialized = 0;
    strata::core::SerialWorker worker([&] { initialized = 1; });
    assert(initialized == 1);
    for (unsigned epoch = 1; epoch <= 2000; ++epoch) {
        strata::core::HostTask task(&worker);
        task.start([&] { for (unsigned i = 0; i < data.size(); ++i) data[i] = i ^ epoch; });
        task.join();
        for (unsigned i = 0; i < data.size(); ++i) assert(data[i] == (i ^ epoch));
    }
    bool caught = false;
    worker.submit([] { throw std::runtime_error("expected"); });
    try { worker.join(); } catch (const std::runtime_error&) { caught = true; }
    assert(caught);
    worker.submit([&] { data[0] = 123; });
    worker.join();
    assert(data[0] == 123);
    bool finished = false;
    { strata::core::SerialWorker draining; draining.submit([&] { finished = true; }); }
    assert(finished);
    caught = false;
    try { strata::core::SerialWorker broken([] { throw std::runtime_error("init"); }); }
    catch (const std::runtime_error&) { caught = true; }
    assert(caught);
    // Both dispatch paths must preserve ordinary stack-reference lifetime.
    for (bool reuse : {false, true}) {
        int result = 0;
        { strata::core::HostTask task(reuse ? &worker : nullptr); task.start([&] { result = 99; }); }
        assert(result == 99);
    }
    std::puts("serial_worker_test: PASS (2000 buffer publications, exceptions, initialization and draining)");
}
