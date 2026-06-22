import { Toaster as SonnerContainer } from "sonner";

export function AppToaster() {
  return (
    <SonnerContainer
      theme="dark"
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group-[.toaster]:glass group-[.toaster]:text-primary group-[.toaster]:border-border/40 group-[.toaster]:shadow-2xl group-[.toaster]:rounded-2xl group-[.toaster]:p-4 group-[.toaster]:font-['Outfit'] group-[.toaster]:tracking-tight",
          description:
            "group-[.toast]:text-secondary group-[.toast]:text-[11px] group-[.toast]:font-bold group-[.toast]:uppercase group-[.toast]:tracking-widest group-[.toast]:mt-1 group-[.toast]:opacity-60",
          actionButton:
            "group-[.toast]:bg-accent group-[.toast]:text-white group-[.toast]:rounded-xl group-[.toast]:px-4 group-[.toast]:h-9 group-[.toast]:font-black group-[.toast]:text-[10px] group-[.toast]:uppercase group-[.toast]:tracking-widest",
          cancelButton:
            "group-[.toast]:bg-white/5 group-[.toast]:text-tertiary group-[.toast]:rounded-xl group-[.toast]:px-4 group-[.toast]:h-9 group-[.toast]:font-black group-[.toast]:text-[10px] group-[.toast]:uppercase group-[.toast]:tracking-widest",
          success:
            "group-[.toaster]:border-success/30 group-[.toaster]:shadow-success/5",
          error:
            "group-[.toaster]:border-danger/30 group-[.toaster]:shadow-danger/5",
          info: "group-[.toaster]:border-info/30 group-[.toaster]:shadow-info/5",
        },
      }}
    />
  );
}
