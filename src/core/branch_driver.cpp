#include "strata/core/branch_driver.hpp"
#include "strata/core/branch_session.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace strata::core {
namespace {
void error_reply(const std::string& message) {
    std::cout << "{\"status\":\"error\",\"message\":\"";
    for (unsigned char c : message) {
        if (c == '"' || c == '\\') std::cout << '\\';
        std::cout << (c < 32 ? ' ' : (char)c);
    }
    std::cout << "\"}" << std::endl;
}
}
int branch_driver(const WeightTable& weights, const ModelGeometry& geometry, SessionState& state,
                  const VerifyHits& hits, const NativeHead* head, PoolMultiFn pool, void* user,
                  bool& pool_failed) {
    std::string error;
    // Images never leave this process; model identity is fixed by its loaded
    // weights. The API validates the external model/build contract before launch.
    BranchSession session(state, geometry, "loaded-model-single-process-v1");
    if (!session.bind(error)) { error_reply(error); return 1; }
    Verifier forward;
    // Strata requires capacity for at least two rows even when run() consumes
    // just one. The actual forced forward below always passes T=1.
    if (!forward.init(weights, geometry, state, hits, head, 2, error)) { error_reply(error); return 1; }
    forward.set_head_sampling(false); // forced inputs; the API owns RNG/grammar
    std::vector<BranchSessionImage> images;
    std::vector<float> logits((size_t)forward.vocab());
    std::cout << "{\"status\":\"ready\",\"vocab\":" << forward.vocab()
              << ",\"capacity\":" << state.max_cells << "}" << std::endl;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream in(line);
        std::string command;
        in >> command;
        error.clear();
        if (command == "quit") {
            std::cout << "{\"status\":\"closed\"}" << std::endl;
            return 0;
        }
        if (command == "reset") {
            if (!session.reset(error)) { error_reply(error); continue; }
            std::cout << "{\"status\":\"ok\",\"consumed\":0}" << std::endl;
        } else if (command == "feed") {
            std::vector<int32_t> tokens;
            int64_t token;
            bool valid = true;
            while (in >> token) {
                if (token < 0 || token >= forward.vocab()) { valid = false; break; }
                tokens.push_back((int32_t)token);
            }
            if (!valid || !in.eof() || tokens.empty() || tokens.size() > (size_t)state.max_cells - session.ids().size()) {
                error_reply("invalid token list or context capacity"); continue;
            }
            bool ok = true;
            for (int32_t t : tokens) {
                const auto position = (int64_t)session.ids().size();
                int32_t unused_sample = 0;
                pool_failed = false;
                if (!session.begin(position, 1, error) ||
                    !forward.run(1, &t, position, pool, user, &unused_sample, error) || pool_failed ||
                    !forward.commit(1, error) || !forward.copy_logits(0, logits.data()) ||
                    !session.finish({t}, logits, error)) { ok = false; break; }
            }
            if (!ok) { error_reply(error.empty() ? "native forward or recurrent commit failed" : error); continue; }
            std::cout << "{\"status\":\"ok\",\"consumed\":" << session.ids().size() << "}" << std::endl;
        } else if (command == "capture") {
            auto image = session.freeze(error);
            if (!image) { error_reply(error); continue; }
            images.push_back(std::move(image));
            std::cout << "{\"status\":\"ok\",\"handle\":" << images.size()-1
                      << ",\"consumed\":" << session.ids().size() << "}" << std::endl;
        } else if (command == "restore" || command == "drop") {
            size_t index;
            std::string extra;
            if (!(in >> index) || (in >> extra) || index >= images.size() || !images[index]) {
                error_reply("missing derived checkpoint handle"); continue;
            }
            if (command == "drop") images[index].reset();
            else if (!session.restore(images[index], error)) { error_reply(error); continue; }
            std::cout << "{\"status\":\"ok\",\"consumed\":" << session.ids().size() << "}" << std::endl;
        } else if (command == "logits") {
            std::string path, extra;
            if (!(in >> path) || (in >> extra) || session.logits().empty()) { error_reply("missing path or frontier"); continue; }
            std::ofstream out(path, std::ios::binary | std::ios::trunc);
            out.write((const char*)session.logits().data(), (std::streamsize)session.logits().size()*sizeof(float));
            out.close();
            if (!out) { error_reply("frontier write failed"); continue; }
            std::cout << "{\"status\":\"ok\",\"bytes\":" << session.logits().size()*sizeof(float) << "}" << std::endl;
        } else if (command == "write") {
            std::string path, extra;
            if (!(in >> std::quoted(path)) || (in >> extra)) { error_reply("missing checkpoint path"); continue; }
            size_t bytes = 0;
            if (!session.write(path, bytes, error)) { error_reply(error); continue; }
            std::cout << "{\"status\":\"ok\",\"bytes\":" << bytes << "}" << std::endl;
        } else if (command == "load") {
            std::string path, ids_path, logits_path, extra;
            if (!(in >> std::quoted(path) >> std::quoted(ids_path) >> std::quoted(logits_path)) || (in >> extra)) {
                error_reply("cold load requires state, exact history and frontier paths"); continue;
            }
            std::ifstream inputs(ids_path);
            std::vector<int32_t> ids;
            int64_t token;
            bool valid = bool(inputs);
            while (inputs >> token) {
                if (token < 0 || token >= forward.vocab() || ids.size() >= (size_t)state.max_cells) {
                    valid = false; break;
                }
                ids.push_back((int32_t)token);
            }
            std::ifstream frontier(logits_path, std::ios::binary | std::ios::ate);
            const auto bytes = (std::streamsize)forward.vocab()*sizeof(float);
            if (!valid || !inputs.eof() || ids.empty() || !frontier || frontier.tellg() != bytes) {
                error_reply("invalid cold history or frontier extent"); continue;
            }
            std::vector<float> next_logits((size_t)forward.vocab());
            frontier.seekg(0);
            frontier.read((char*)next_logits.data(), bytes);
            if (!frontier) { error_reply("incomplete cold frontier"); continue; }
            if (!session.load(path, ids, next_logits, error)) { error_reply(error); continue; }
            std::cout << "{\"status\":\"ok\",\"consumed\":" << session.ids().size() << "}" << std::endl;
        } else if (command == "audit") {
            size_t index;
            std::string path, extra;
            if (!(in >> index >> std::quoted(path)) || (in >> extra) || index >= images.size() || !images[index]) {
                error_reply("audit requires a retained handle and output path"); continue;
            }
            BranchSessionAudit result;
            if (!session.audit(images[index], path, result, error)) { error_reply(error); continue; }
            std::cout << "{\"status\":\"ok\",\"bytes\":" << result.bytes << ",\"consumed\":" << result.consumed
                      << ",\"qsa_page_cells\":" << result.qsa_page_cells
                      << ",\"index_block_cells\":" << result.index_block_cells
                      << ",\"allocation_page_bytes\":" << vmm_granularity() << ",\"regions\":[";
            bool first = true;
            for (const auto& r : result.regions) {
                if (!first) std::cout << ',';
                first = false;
                std::cout << "{\"kind\":\"" << r.kind << "\",\"offset\":" << r.offset << ",\"bytes\":" << r.bytes
                          << ",\"pool\":" << r.pool << ",\"qsa_ordinal\":" << r.qsa_ordinal
                          << ",\"pool_offset\":" << r.pool_offset << ",\"bytes_per_cell\":" << r.bytes_per_cell
                          << ",\"filled_prefix_bytes\":" << r.filled_prefix_bytes
                          << ",\"allocation_id\":" << r.page.allocation_id << ",\"driver_handle\":" << r.page.driver_handle
                          << ",\"owners\":" << r.page.owners << '}';
            }
            std::cout << "]}" << std::endl;
        } else if (command == "pages") {
            std::cout << "{\"status\":\"ok\",\"pages\":[";
            bool first = true;
            for (const auto& page : session.ownership()) {
                if (!first) std::cout << ',';
                first = false;
                std::cout << '[' << page.allocation_id << ',' << page.driver_handle << ',' << page.owners << ',' << page.bytes
                          << ",\"" << page.kind << "\"," << page.pool << ']';
            }
            std::cout << "]}" << std::endl;
        } else if (command == "stats") {
            const auto p = BranchPages::counters();
            const auto s = session.counters();
            const auto e = vmm_failure_counters();
            std::cout << "{\"status\":\"ok\",\"consumed\":" << session.ids().size()
                      << ",\"forward_tokens\":" << forward.completed_forward_tokens
                      << ",\"windows\":" << forward.windows
                      << ",\"allocations\":" << p.allocations << ",\"releases\":" << p.releases
                      << ",\"live_bytes\":" << p.live_bytes << ",\"cow_pages\":" << p.cow_pages
                      << ",\"copied_bytes\":" << p.copied_bytes << ",\"mappings\":" << p.mappings
                      << ",\"unmappings\":" << p.unmappings
                      << ",\"address_reservations\":" << p.address_reservations
                      << ",\"address_releases\":" << p.address_releases
                      << ",\"vmm_driver_failures\":" << e.driver_failures
                      << ",\"vmm_out_of_memory_failures\":" << e.out_of_memory_failures
                      << ",\"vmm_last_driver_error\":" << e.last_error
                      << ",\"vmm_last_failed_operation\":\"" << e.last_operation << "\""
                      << ",\"audit_read_bytes\":" << p.audit_read_bytes
                      << ",\"binding_copy_bytes\":" << s.binding_copy_bytes
                      << ",\"saved_running_bytes\":" << s.saved_running_bytes
                      << ",\"restored_running_bytes\":" << s.restored_running_bytes
                      << ",\"written_file_bytes\":" << s.written_file_bytes
                      << ",\"loaded_file_bytes\":" << s.loaded_file_bytes
                      << ",\"captures\":" << s.captures << ",\"restores\":" << s.restores << "}" << std::endl;
        } else error_reply("unknown command");
    }
    return 0;
}
} // namespace strata::core
