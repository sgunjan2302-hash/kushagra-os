// Kushagra OS - Modern Floating Layout (Studio / macOS Mode)
// Plasma 6 Wayland Desktop Script
// Top status bar + Centered floating bottom dock with auto-dodge
// Note: Global Menu (org.kde.plasma.appmenu) is intentionally omitted by default due to
// upstream Wayland GTK3/4, native Electron (VS Code, Discord), and Firefox menubar caveats.

var allPanels = panels();
for (var i = 0; i < allPanels.length; i++) {
    allPanels[i].remove();
}

// 1. Top Bar: Global launcher, centered clock, and system tray
var topBar = new Panel();
topBar.location = "top";
topBar.height = 32;
topBar.lengthMode = "fill"; // String lengthMode per Plasma 6 API
topBar.floating = false;
topBar.hiding = "none";

topBar.addWidget("org.kde.plasma.kickoff");
topBar.addWidget("org.kde.plasma.marginsseparator");
topBar.addWidget("org.kde.plasma.digitalclock");
topBar.addWidget("org.kde.plasma.marginsseparator");
topBar.addWidget("org.kde.plasma.systemtray");

// 2. Bottom Floating Dock: Centered, auto-hides when windows overlap (dodgewindows)
var dock = new Panel();
dock.location = "bottom";
dock.height = 56;
dock.lengthMode = "fit"; // String lengthMode per Plasma 6 API
dock.alignment = "center";
dock.floating = true;
dock.hiding = "dodgewindows";

dock.addWidget("org.kde.plasma.icontasks");
