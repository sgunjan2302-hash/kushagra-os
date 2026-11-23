// Kushagra OS - Windows Classic Layout (Familiar Mode)
// Plasma 6 Wayland Desktop Script
// Removes existing panels and configures a standard bottom-docked taskbar

var allPanels = panels();
for (var i = 0; i < allPanels.length; i++) {
    allPanels[i].remove();
}

var panel = new Panel();
panel.location = "bottom";
panel.height = 44;
panel.lengthMode = "fill"; // String lengthMode per Plasma 6 API
panel.alignment = "left";
panel.floating = false;
panel.hiding = "none";

// Core desktop widgets
panel.addWidget("org.kde.plasma.kickoff");
panel.addWidget("org.kde.plasma.pager");
panel.addWidget("org.kde.plasma.icontasks");
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
