# -*- coding: utf-8 -*-
"""Windows 平台加速：避免 pyreadline3 触发 platform._wmi_query 导致的 WMI 查询阻塞"""
import platform

if hasattr(platform, "_wmi_query"):
    platform._wmi_query = lambda *a, **k: ("10.0.22631", 1, "Multiprocessor Free", 0, 0)
