# Maintenance dependencies

This one-off local archive helper uses Node.js 25.8.0 and only its built-in modules. No third-party Node packages are installed or required.

It uses existing macOS system utilities at /usr/bin/git, /usr/bin/tar (BSD tar with permission-preserving -xzpf), /usr/bin/du, /usr/sbin/lsof and /bin/ps. These retain the established Git, archive-format, disk-accounting and process-inspection behavior without adding software. Missing commands or unsuccessful checks abort the operation. The helper is specific to this local workspace and is retained as an execution record. Restoration can use a compatible tar/gzip utility and the immutable manifest.
