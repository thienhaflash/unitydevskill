// Skeleton of a device harness for game-profile-optimize (protocol: reference/harness-protocol.md). UNTESTED as a whole: compile it in your project, fill the TODO hooks, and
// check the log lines against scripts/record.py before the first sweep. Keep it in a dev-only script behind a scripting define (below) and never in the Editor.
#if PERF_DEVICE_RUN && !UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public sealed class DeviceRun : MonoBehaviour
{
    const string Tag = "MYGAMEPERF"; // = "logTag" in profile.json

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot()
    {
        if (Extra("units") == null && Extra("ab") == null) return; // a normal launch: do nothing
        new GameObject("DeviceRun").AddComponent<DeviceRun>();
    }

    // intent extras: adb shell am start ... --es key value   (device-run.sh key=value)
    static string Extra(string key)
    {
#if UNITY_ANDROID
        using var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
        using var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
        using var intent = activity.Call<AndroidJavaObject>("getIntent");
        return intent.Call<bool>("hasExtra", key) ? intent.Call<string>("getStringExtra", key) : null;
#else
        return null;
#endif
    }

    IEnumerator Start()
    {
        Application.targetFrameRate = Screen.currentResolution.refreshRate; // measure at the display's rate
        Debug.Log($"{Tag} DEVICE {SystemInfo.deviceModel} | {SystemInfo.graphicsDeviceName} {SystemInfo.graphicsDeviceType} | {Screen.width}x{Screen.height} @{Screen.currentResolution.refreshRate}Hz" +
                  $" | quality {QualitySettings.names[QualitySettings.GetQualityLevel()]} (shadows {QualitySettings.shadows}) | kw  | scale 1 | cpu {SystemInfo.processorCount}x {SystemInfo.processorType} | ram {SystemInfo.systemMemorySize} MB");
        var units = (Extra("units") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries);
        var secs = float.TryParse(Extra("secs"), out var s) ? s : 5f;
        var level = Extra("quality");
        if (level != null) { /* TODO: pin the game's quality level to `level` */ }
        if (Extra("noauto") != null) { /* TODO: disable the game's automatic quality step-down */ }
        var switches = (Extra("ab") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries);

        foreach (var unit in units)
        {
            yield return LoadUnit(unit); // TODO: start a FRESH game for this unit (a shared session may end halfway)
            if (switches.Length > 0)
            {
                foreach (var sw in switches) yield return AB(unit, sw);
            }
            else
            {
                foreach (var section in Sections()) // TODO: the sections of the profile, in order
                {
                    yield return GoToSection(section);
                    yield return Measure($"{unit} {section}", secs);
                }
            }
            if (Extra("shots") != null) { Debug.Log($"{Tag} SHOT {unit}"); yield return new WaitForSeconds(1.5f); }
        }
        Debug.Log($"{Tag} DONE");
    }

    // plain section: one line per unit and section
    IEnumerator Measure(string label, float seconds)
    {
        var ms = new List<float>();
        var end = Time.realtimeSinceStartup + seconds;
        while (Time.realtimeSinceStartup < end) { ms.Add(Time.unscaledDeltaTime * 1000f); yield return null; }
        ms.RemoveAt(0);
        var sorted = ms.OrderBy(x => x).ToArray();
        var n = sorted.Length;
        Debug.Log($"{Tag} {label}: frames {n} fps {n / seconds:F1} avg {ms.Average():F1} p50 {sorted[n / 2]:F1} p95 {sorted[(int)(n * .95f)]:F1} p99 {sorted[(int)(n * .99f)]:F1} max {sorted[n - 1]:F1}" +
                  $" | drops>20ms {ms.Count(x => x > 20f)} >33ms {ms.Count(x => x > 33f)}");
    }

    // interleaved on/off: the OFF side must be the untreated state
    IEnumerator AB(string unit, string sw)
    {
        var gpu = new float[2]; var fps = new float[2]; var blocks = 4; var seconds = 2f;
        for (var b = 0; b < blocks; b++)
            for (var side = 0; side < 2; side++)
            {
                Treat(sw, on: side == 1);
                yield return new WaitForSeconds(0.5f); // let the treatment settle
                var frames = 0; var g = 0f; var timings = new FrameTiming[1];
                var end = Time.realtimeSinceStartup + seconds;
                while (Time.realtimeSinceStartup < end)
                {
                    FrameTimingManager.CaptureFrameTimings();
                    if (FrameTimingManager.GetLatestTimings(1, timings) > 0) g += (float)timings[0].gpuFrameTime;
                    frames++; yield return null;
                }
                gpu[side] += g / frames; fps[side] += frames / seconds;
            }
        Treat(sw, on: false);
        Debug.Log($"{Tag} AB-RESULT {unit} {sw}: off gpu {gpu[0] / blocks:F1} ms fps {fps[0] / blocks:F1} | ON gpu {gpu[1] / blocks:F1} ms fps {fps[1] / blocks:F1} | delta {(gpu[1] - gpu[0]) / blocks:F1} ms");
    }

    // one named switch per case; `on` = the treatment is applied (the thing is switched OFF in the game), !on restores the exact baseline
    void Treat(string name, bool on)
    {
        switch (name)
        {
            // TODO: e.g. case "particles_off": foreach (var r in FindObjectsByType<ParticleSystemRenderer>(FindObjectsSortMode.None)) r.enabled = !on; break;
            default: Debug.Log($"{Tag} FAIL unknown switch {name}"); break;
        }
    }

    IEnumerator LoadUnit(string id) { yield break; }          // TODO
    IEnumerable<string> Sections() { yield break; }            // TODO
    IEnumerator GoToSection(string section) { yield break; }   // TODO
}
#endif
