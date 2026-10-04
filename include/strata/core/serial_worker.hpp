#pragma once

#include <condition_variable>
#include <exception>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>

namespace strata::core {

// One host task at a time. submit/join have one calling thread. join publishes
// every task write before the caller consumes it; destruction drains the task.
// No CUDA work or scheduling policy is hidden in this helper.
class SerialWorker {
public:
    explicit SerialWorker(std::function<void()> initialize = {}) {
        thread_ = std::thread([this, initialize = std::move(initialize)] {
            std::exception_ptr error;
            try { if (initialize) initialize(); } catch (...) { error = std::current_exception(); }
            std::unique_lock<std::mutex> lock(mu_);
            error_ = error;
            ready_ = true;
            done_cv_.notify_one();
            if (error) return;
            for (;;) {
                work_cv_.wait(lock, [this] { return pending_ || stop_; });
                if (stop_) return;
                auto task = std::move(task_);
                lock.unlock();
                error = nullptr;
                try { task(); } catch (...) { error = std::current_exception(); }
                // Destroy captures while the caller still waits for completion.
                task = {};
                lock.lock();
                error_ = error;
                pending_ = false;
                done_cv_.notify_one();
            }
        });
        std::unique_lock<std::mutex> lock(mu_);
        done_cv_.wait(lock, [this] { return ready_; });
        if (error_) {
            const auto error = error_;
            lock.unlock();
            thread_.join();
            std::rethrow_exception(error);
        }
    }

    ~SerialWorker() {
        {
            std::unique_lock<std::mutex> lock(mu_);
            done_cv_.wait(lock, [this] { return !pending_; });
            stop_ = true;
        }
        work_cv_.notify_one();
        if (thread_.joinable()) thread_.join();
    }

    SerialWorker(const SerialWorker&) = delete;
    SerialWorker& operator=(const SerialWorker&) = delete;

    void submit(std::function<void()> task) {
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (pending_ || stop_) throw std::logic_error("SerialWorker: task already pending or stopped");
            task_ = std::move(task);
            error_ = nullptr;
            pending_ = true;
        }
        work_cv_.notify_one();
    }

    void join() {
        std::unique_lock<std::mutex> lock(mu_);
        done_cv_.wait(lock, [this] { return !pending_; });
        if (error_) std::rethrow_exception(error_);
    }

private:
    std::mutex mu_;
    std::condition_variable work_cv_, done_cv_;
    std::function<void()> task_;
    std::exception_ptr error_;
    std::thread thread_;
    bool ready_ = false, pending_ = false, stop_ = false;
};

// Keeps the existing per-window launch/join shape. Null worker is exactly a
// normal std::thread; the opt-in branch reuses a worker without removing join.
class HostTask {
public:
    explicit HostTask(SerialWorker* worker = nullptr) : worker_(worker) {}
    ~HostTask() { if (active_) join(); }
    HostTask(const HostTask&) = delete;
    HostTask& operator=(const HostTask&) = delete;

    template<class F> void start(F&& task) {
        if (active_) throw std::logic_error("HostTask: already active");
        if (worker_) worker_->submit(std::forward<F>(task));
        else thread_ = std::thread(std::forward<F>(task));
        active_ = true;
    }
    bool joinable() const { return active_; }
    void join() {
        if (!active_) return;
        // Clear first so an exception cannot cause the destructor to rethrow.
        active_ = false;
        if (worker_) worker_->join();
        else thread_.join();
    }
private:
    SerialWorker* worker_;
    std::thread thread_;
    bool active_ = false;
};

} // namespace strata::core
