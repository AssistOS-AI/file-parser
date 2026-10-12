// GB10 memory probe (plan Phase 1: repeat the review's M1-M6 inside a nested agent container).
// usage: probe <hold_gib> <hold_seconds> [oom_adj]
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <vector>
#include <thread>
static long mi(const char *key) {
  FILE *f = fopen("/proc/meminfo", "r"); char line[256]; long v = -1; size_t n = strlen(key);
  while (f && fgets(line, sizeof line, f)) if (!strncmp(line, key, n) && line[n] == ':') { v = atol(line + n + 1); break; }
  if (f) fclose(f); return v; }
static void meminfo(const char *tag) {
  size_t fr = 0, tot = 0; cudaMemGetInfo(&fr, &tot);
  printf("%-10s MemFree %.2f MemAvailable %.2f Cached %.2f GiB | cudaMemGetInfo free %.2f total %.2f GiB\n", tag,
         mi("MemFree") / 1048576.0, mi("MemAvailable") / 1048576.0, mi("Cached") / 1048576.0, fr / 1073741824.0, tot / 1073741824.0); }
static void selfinfo(const char *tag) {
  char buf[256]; FILE *f = fopen("/proc/self/status", "r");
  while (f && fgets(buf, sizeof buf, f)) if (!strncmp(buf, "VmRSS", 5)) printf("%-10s %s", tag, buf);
  if (f) fclose(f);
  f = fopen("/proc/self/oom_score", "r"); if (f && fgets(buf, sizeof buf, f)) printf("%-10s oom_score %s", tag, buf); if (f) fclose(f);
  f = fopen("/proc/self/oom_score_adj", "r"); if (f && fgets(buf, sizeof buf, f)) printf("%-10s oom_score_adj %s", tag, buf); if (f) fclose(f);
  f = fopen("/sys/fs/cgroup/memory.current", "r"); if (f && fgets(buf, sizeof buf, f)) printf("%-10s cgroup memory.current %.1f MiB\n", tag, atof(buf) / 1048576.0); else printf("%-10s cgroup memory.current unreadable\n", tag); if (f) fclose(f); }
int main(int argc, char **argv) {
  int hold = argc > 1 ? atoi(argv[1]) : 4, secs = argc > 2 ? atoi(argv[2]) : 2;
  if (argc > 3) { FILE *f = fopen("/proc/self/oom_score_adj", "w"); if (f) { fprintf(f, "%s", argv[3]); fclose(f); } else perror("oom_score_adj"); }
  cudaDeviceProp p; if (cudaGetDeviceProperties(&p, 0) != cudaSuccess) { printf("no CUDA device\n"); return 1; }
  printf("device %s cc %d.%d integrated=%d pageableMemoryAccessUsesHostPageTables=%d totalGlobalMem %.2f GiB\n", p.name, p.major, p.minor,
         p.integrated, p.pageableMemoryAccessUsesHostPageTables, p.totalGlobalMem / 1073741824.0);
  int drv = 0, rt = 0; cudaDriverGetVersion(&drv); cudaRuntimeGetVersion(&rt); printf("driver API %d runtime %d\n", drv, rt);
  meminfo("before"); selfinfo("before");
  std::vector<void *> ptrs; auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < hold; i++) { void *q = nullptr; if (cudaMalloc(&q, 1ull << 30) != cudaSuccess) { printf("cudaMalloc failed at %d GiB\n", i); break; }
    cudaMemset(q, 1, 1ull << 30); ptrs.push_back(q); }
  cudaDeviceSynchronize();
  double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  printf("allocated+touched %zu GiB in %.3f s = %.1f GiB/s\n", ptrs.size(), s, ptrs.size() / s);
  meminfo("holding"); selfinfo("holding");
  std::this_thread::sleep_for(std::chrono::seconds(secs));
  for (void *q : ptrs) cudaFree(q);
  meminfo("freed");
  return 0; }
