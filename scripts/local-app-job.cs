using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

// A job owns descendants even when npm exits before its server does. The supervisor
// joins before spawning anything. Closing its last job handle cleans up the attempt.
public sealed class LocalAppJob : IDisposable
{
    private readonly SafeFileHandle handle;

    private LocalAppJob(SafeFileHandle handle) { this.handle = handle; }

    public static LocalAppJob Create(string name)
    {
        SafeFileHandle handle = CreateJobObject(IntPtr.Zero, name);
        if (handle.IsInvalid) throw new Win32Exception();
        if (Marshal.GetLastWin32Error() == 183)
        {
            handle.Dispose();
            throw new InvalidOperationException("A launcher job with this name already exists.");
        }
        var job = new LocalAppJob(handle);
        try
        {
            var limits = new ExtendedLimits();
            limits.Basic.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(handle, 9, ref limits, Marshal.SizeOf(limits)))
                throw new Win32Exception();
            using (Process self = Process.GetCurrentProcess())
                if (!AssignProcessToJobObject(handle, self.Handle)) throw new Win32Exception();
            return job;
        }
        catch { job.Dispose(); throw; }
    }

    public static bool Contains(string name, int processId)
    {
        using (SafeFileHandle job = OpenJobObject(4, false, name))
        {
            if (job.IsInvalid) throw new Win32Exception();
            try
            {
                using (Process process = Process.GetProcessById(processId))
                {
                    bool member;
                    if (!IsProcessInJob(process.Handle, job, out member)) throw new Win32Exception();
                    return member;
                }
            }
            catch (ArgumentException) { return false; }
        }
    }

    public static bool Stop(string name, int ownerId, long creationTicks)
    {
        using (SafeFileHandle job = OpenJobObject(4 | 8, false, name))
        {
            if (job.IsInvalid)
            {
                int error = Marshal.GetLastWin32Error();
                if (error == 2) return false;
                throw new Win32Exception(error);
            }
            try
            {
                using (Process owner = Process.GetProcessById(ownerId))
                {
                    // Hold the process handle across validation and termination, so PID
                    // reuse cannot change the process whose creation time we checked.
                    IntPtr processHandle = owner.Handle;
                    if (owner.StartTime.ToUniversalTime().Ticks != creationTicks) return false;
                    bool member;
                    if (!IsProcessInJob(processHandle, job, out member)) throw new Win32Exception();
                    if (!member) return false;
                    if (!TerminateJobObject(job, 0)) throw new Win32Exception();
                    if (!owner.WaitForExit(5000)) throw new InvalidOperationException("Could not confirm supervisor exit.");
                    return true;
                }
            }
            catch (ArgumentException) { return false; }
        }
    }

    public void Dispose() { handle.Dispose(); }

    [StructLayout(LayoutKind.Sequential)]
    private struct BasicLimits
    {
        public long ProcessTime, JobTime;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IoCounters
    {
        public ulong ReadOperations, WriteOperations, OtherOperations;
        public ulong ReadBytes, WriteBytes, OtherBytes;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ExtendedLimits
    {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemory, PeakJobMemory;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle OpenJobObject(uint access, bool inherit, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(SafeFileHandle job, int kind, ref ExtendedLimits limits, int size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool IsProcessInJob(IntPtr process, SafeFileHandle job, out bool member);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool TerminateJobObject(SafeFileHandle job, uint exitCode);
}
