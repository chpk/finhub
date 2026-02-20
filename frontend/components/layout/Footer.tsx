export function Footer() {
  return (
    <footer className="border-t border-gray-100 bg-white/50 py-6">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6">
        <p className="text-xs text-muted-foreground">
          NFRA Compliance Engine &copy; {new Date().getFullYear()}
        </p>
        <p className="text-xs text-muted-foreground">
          Built for IndiaAI &times; NFRA Challenge
        </p>
      </div>
    </footer>
  );
}
