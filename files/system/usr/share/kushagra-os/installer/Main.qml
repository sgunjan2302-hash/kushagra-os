import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: root
    visible: false
    visibility: Window.FullScreen
    flags: Qt.Window
    color: "#060913"
    title: "Kushagra OS Installer"

    onClosing: function(close) {
        if (!isPreviewMode && !installerBackend.launchingDesktop) {
            close.accepted = false
        }
    }

    property int currentStep: 0 // 0=Welcome, 1=Storage, 2=Confirm, 3=Progress
    property string uiLang: "en_IN" // "en_IN" | "hi_IN"
    property bool isHindi: uiLang === "hi_IN"
    property var selectedTarget: null
    property bool confirmChecked: false
    property bool logsExpanded: false

    palette.windowText: "#FFFFFF"
    palette.text: "#FFFFFF"
    palette.buttonText: "#FFFFFF"
    palette.button: "#1E293B"

    component GlassButton: Button {
        id: btn
        implicitWidth: Math.max(64, btnLabel.implicitWidth + leftPadding + rightPadding)
        implicitHeight: 40
        leftPadding: 16
        rightPadding: 16
        topPadding: 8
        bottomPadding: 8
        font.pixelSize: 13
        font.weight: btn.highlighted ? Font.Bold : Font.Medium
        opacity: btn.enabled ? 1.0 : 0.45

        background: Rectangle {
            radius: 10
            color: btn.highlighted
                   ? (btn.down ? "#55FF9933" : (btn.hovered ? "#44FF9933" : "#30FF9933"))
                   : (btn.down ? "#2B3A55" : (btn.hovered ? "#28FFFFFF" : "#18FFFFFF"))
            border.color: btn.highlighted ? "#FF9933" : "#38FFFFFF"
            border.width: btn.highlighted ? 1.5 : 1
        }

        contentItem: Text {
            id: btnLabel
            text: btn.text
            font: btn.font
            color: btn.enabled ? "#FFFFFF" : "#94A3B8"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    component GlassCheckBox: CheckBox {
        id: cb
        spacing: 12
        font.pixelSize: 13

        indicator: Rectangle {
            implicitWidth: 22
            implicitHeight: 22
            x: cb.leftPadding
            y: parent.height / 2 - height / 2
            radius: 6
            color: cb.checked ? "#FF9933" : "#1E293B"
            border.color: cb.checked ? "#FF9933" : (cb.hovered ? "#FF9933" : "#64748B")
            border.width: 2

            Text {
                anchors.centerIn: parent
                visible: cb.checked
                text: "✓"
                color: "#060913"
                font.pixelSize: 14
                font.weight: Font.Bold
            }
        }

        contentItem: Text {
            text: cb.text
            font: cb.font
            color: "#FFFFFF"
            wrapMode: Text.WordWrap
            verticalAlignment: Text.AlignVCenter
            leftPadding: cb.indicator.width + cb.spacing
        }
    }

    Connections {
        target: installerBackend
        function onRecommendedTargetIdChanged() {
            root.pickRecommendedTarget()
        }
        function onDisksChanged() {
            root.pickRecommendedTarget()
        }
        function onInstallErrorChanged() {
            if (installerBackend.installError.length > 0) {
                root.logsExpanded = true
            }
        }
    }

    function pickRecommendedTarget() {
        var recId = installerBackend.recommendedTargetId
        if (!recId) {
            root.selectedTarget = null
            return
        }
        var ds = installerBackend.disks
        for (var i = 0; i < ds.length; i++) {
            var segs = ds[i].segments || []
            for (var j = 0; j < segs.length; j++) {
                if (segs[j].id === recId && segs[j].selectable) {
                    root.selectedTarget = segs[j]
                    return
                }
            }
        }
        root.selectedTarget = null
    }

    function segmentColor(seg) {
        if (seg.isEsp) return "#38BDF8"
        if (seg.isWindows) return "#6366F1"
        if (seg.isLive) return "#EF4444"
        if (seg.kind === "unallocated" && seg.selectable) return "#22C55E"
        if (seg.selectable) return "#F59E0B"
        return "#475569"
    }

    // Ambient dark-glass backdrop matching Stage 2 kushagra-setup
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#060913" }
            GradientStop { position: 0.55; color: "#0C1528" }
            GradientStop { position: 1.0; color: "#08121A" }
        }
        Rectangle {
            width: 580; height: 580; radius: 290
            x: -160; y: -180
            color: "#18FF9933"
        }
        Rectangle {
            width: 540; height: 540; radius: 270
            x: parent.width - 360; y: parent.height - 340
            color: "#14138808"
        }
    }

    Rectangle {
        id: glassCard
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 980)
        height: Math.min(parent.height - 72, 680)
        radius: 24
        color: "#CC0F172A"
        border.color: "#2EFFFFFF"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 34
            spacing: 18

            // Top Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Image {
                    source: kushagraLogoUrl
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 42
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "KUSHAGRA OS · K-INSTALLER"
                        color: "#FFFFFF"
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        font.letterSpacing: 1.6
                    }
                    Text {
                        text: isHindi ? "स्टेज 1 इंस्टॉलर · ड्यूल-बूट सुरक्षित (Btrfs + UEFI)" : "STAGE 1 OEM INSTALLER · DUAL-BOOT SAFE (BTRFS + UEFI)"
                        color: "#94A3B8"
                        font.pixelSize: 11
                        font.letterSpacing: 1.1
                    }
                }

                Item { Layout.fillWidth: true }

                Row {
                    spacing: 6
                    GlassButton {
                        implicitHeight: 34
                        text: "EN"
                        highlighted: root.uiLang === "en_IN"
                        onClicked: root.uiLang = "en_IN"
                    }
                    GlassButton {
                        implicitHeight: 34
                        text: "हिन्दी"
                        highlighted: root.uiLang === "hi_IN"
                        onClicked: root.uiLang = "hi_IN"
                    }
                }

                Row {
                    spacing: 8
                    Repeater {
                        model: 4
                        Rectangle {
                            width: index === root.currentStep ? 28 : 10
                            height: 8
                            radius: 4
                            color: index === root.currentStep ? "#FF9933" : (index < root.currentStep ? "#138808" : "#33FFFFFF")
                            Behavior on width { NumberAnimation { duration: 180 } }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1FFFFFFF" }

            // Dynamic Views
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: root.currentStep

                // =============================================================
                // SCREEN 0: LiveCD Welcome (Install vs Try Live Desktop)
                // =============================================================
                ColumnLayout {
                    spacing: 20

                    Text {
                        text: isHindi ? "कुशाग्र ओएस (Live Environment)" : "Welcome to Kushagra OS"
                        color: "#FFFFFF"; font.pixelSize: 32; font.weight: Font.Bold
                    }
                    Text {
                        text: isHindi
                              ? "आप अभी लाइव USB से चल रहे हैं। हार्ड ड्राइव पर सुरक्षित इंस्टॉल शुरू करें, या पहले लाइव डेस्कटॉप आज़माएं।"
                              : "You are running the live USB environment. Install Kushagra OS safely alongside Windows, or explore the desktop first."
                        color: "#CBD5E1"; font.pixelSize: 15; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.topMargin: 8
                        spacing: 20

                        // Install Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 18
                            color: "#22FF9933"
                            border.color: "#FF9933"
                            border.width: 2

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 12
                                Text { text: isHindi ? "सुझाया गया · चरण 1" : "RECOMMENDED · STAGE 1"; color: "#FF9933"; font.pixelSize: 12; font.weight: Font.Bold }
                                Text { text: isHindi ? "Install Kushagra OS (इंस्टॉल करें)" : "Install Kushagra OS"; color: "#FFFFFF"; font.pixelSize: 24; font.weight: Font.Bold }
                                Text {
                                    text: isHindi
                                          ? "• खाली जगह (Unallocated Space) या चुने हुए गैर-Windows पार्टीशन में इंस्टॉल करें।\n• मौजूदा Windows NTFS और EFI पार्टीशन लॉक व सुरक्षित रहते हैं।\n• इंस्टॉल के बाद रीस्टार्ट पर आपका Setup Wizard (kushagra-setup) खुलेगा।"
                                          : "• Installs into Unallocated free space or a single chosen non-Windows partition.\n• Windows NTFS, BitLocker, Live USB & EFI partitions are automatically protected.\n• Reboots straight into Kushagra Setup Wizard (kushagra-setup) to create your account."
                                    color: "#E2E8F0"; font.pixelSize: 13; lineHeight: 1.4; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                                Item { Layout.fillHeight: true }
                                GlassButton {
                                    text: isHindi ? "ड्राइव चयन पर जाएं →" : "Install Kushagra OS →"
                                    highlighted: true
                                    enabled: !installerBackend.launchingDesktop
                                    Layout.fillWidth: true
                                    onClicked: {
                                        root.currentStep = 1
                                        installerBackend.scanDrives()
                                    }
                                }
                            }
                        }

                        // Try Live Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 18
                            color: "#12FFFFFF"
                            border.color: "#2EFFFFFF"
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 12
                                Text { text: isHindi ? "लाइव टेस्टिंग" : "EXPLORE LIVE"; color: "#38BDF8"; font.pixelSize: 12; font.weight: Font.Bold }
                                Text { text: isHindi ? "Try Live Desktop (डेस्कटॉप आज़माएं)" : "Try Live Desktop"; color: "#FFFFFF"; font.pixelSize: 24; font.weight: Font.Bold }
                                Text {
                                    text: isHindi
                                          ? "• बिना हार्ड डिस्क बदले KDE Plasma 6 (Wayland), Wi-Fi, और हार्डवेयर टेस्ट करें।\n• आप बाद में डेस्कटॉप पर मौजूद 'Install Kushagra OS' आइकन से कभी भी इंस्टॉल शुरू कर सकते हैं।"
                                          : "• Test KDE Plasma 6 Wayland, Wi-Fi, Fcitx5 Hindi typing & hardware without touching your drive.\n• Launch the installer anytime using the desktop icon."
                                    color: "#CBD5E1"; font.pixelSize: 13; lineHeight: 1.4; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                                Item { Layout.fillHeight: true }
                                GlassButton {
                                    text: isHindi ? "लाइव डेस्कटॉप पर जाएं" : "Try Live Desktop"
                                    enabled: !installerBackend.launchingDesktop
                                    Layout.fillWidth: true
                                    onClicked: installerBackend.tryLiveDesktop()
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: isHindi
                                  ? "नोट: यदि आप कस्टम LVM/LUKS एन्क्रिप्शन चाहते हैं, तो क्लासिक Fedora Anaconda खोलें।"
                                  : "Need custom LVM/LUKS layout? Use Classic Fedora Anaconda."
                            color: "#94A3B8"; font.pixelSize: 12
                        }
                        Item { Layout.fillWidth: true }
                        GlassButton {
                            text: isHindi ? "क्लासिक Anaconda खोलें (liveinst)" : "Classic Anaconda (liveinst)"
                            enabled: !installerBackend.launchingDesktop
                            onClicked: installerBackend.launchClassicAnaconda()
                        }
                    }
                }

                // =============================================================
                // SCREEN 1: Visual Drive & Partition Selector
                // =============================================================
                ColumnLayout {
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            spacing: 2
                            Text {
                                text: isHindi ? "सुरक्षित ड्राइव और पार्टीशन चुनें" : "Select Installation Target"
                                color: "#FFFFFF"; font.pixelSize: 24; font.weight: Font.Bold
                            }
                            Text {
                                text: isHindi
                                      ? "Windows NTFS, EFI और Live USB स्वचालित रूप से लॉक हैं। केवल हरे (Unallocated) या गैर-Windows स्लॉट ही चुने जा सकते हैं।"
                                      : "Windows NTFS, EFI & Live USB are locked against wipe. Pick Unallocated free space (recommended) or an eligible non-Windows partition."
                                color: "#94A3B8"; font.pixelSize: 12; wrapMode: Text.WordWrap
                            }
                        }
                        Item { Layout.fillWidth: true }
                        GlassButton {
                            text: installerBackend.scanning ? (isHindi ? "स्कैन..." : "Scanning...") : (isHindi ? "रीफ्रेश ड्राइव" : "Refresh Drives")
                            enabled: !installerBackend.scanning
                            onClicked: installerBackend.scanDrives()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(38, scanErrLabel.implicitHeight + 16)
                        radius: 10
                        visible: installerBackend.scanError.length > 0
                        color: "#33F59E0B"
                        border.color: "#F59E0B"
                        Text {
                            id: scanErrLabel
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12
                            wrapMode: Text.WordWrap
                            color: "#FDE68A"; font.pixelSize: 12
                            text: installerBackend.scanError
                        }
                    }

                    ScrollView {
                        id: diskScrollView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        ColumnLayout {
                            width: Math.max(200, diskScrollView.availableWidth)
                            spacing: 14

                            Repeater {
                                model: installerBackend.disks

                                delegate: Rectangle {
                                    id: diskCard
                                    property real diskTotalBytes: Math.max(1, Number(modelData.sizeBytes || 1))
                                    Layout.fillWidth: true
                                    implicitHeight: diskCol.implicitHeight + 24
                                    radius: 14
                                    color: modelData.isLiveMedia ? "#12EF4444" : "#12FFFFFF"
                                    border.color: modelData.isLiveMedia ? "#55EF4444" : "#26FFFFFF"

                                    ColumnLayout {
                                        id: diskCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                                        anchors.margins: 12
                                        spacing: 10

                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                text: (modelData.model || "Local Disk") + " · " + modelData.path + " (" + modelData.sizeLabel + ", " + (modelData.pttype || "unknown").toUpperCase() + ")"
                                                color: "#FFFFFF"; font.pixelSize: 14; font.weight: Font.Bold
                                            }
                                            Item { Layout.fillWidth: true }
                                            Rectangle {
                                                visible: modelData.isLiveMedia
                                                radius: 6; color: "#44EF4444"; border.color: "#EF4444"
                                                implicitWidth: liveLockLbl.implicitWidth + 14; implicitHeight: 24
                                                Text { id: liveLockLbl; anchors.centerIn: parent; text: "🔒 " + modelData.lockedReason; color: "#FCA5A5"; font.pixelSize: 11; font.weight: Font.Bold }
                                            }
                                        }

                                        // Proportional Partition Map Bar
                                        RowLayout {
                                            Layout.fillWidth: true
                                            visible: !modelData.isLiveMedia && (modelData.segments || []).length > 0
                                            spacing: 3
                                            Repeater {
                                                model: modelData.segments || []
                                                delegate: Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.minimumWidth: 18
                                                    Layout.maximumWidth: 520
                                                    Layout.preferredWidth: Math.max(24, Math.min(480, Math.round(((modelData.sizeBytes || 0) / diskCard.diskTotalBytes) * 760)))
                                                    height: 16
                                                    radius: 4
                                                    color: root.segmentColor(modelData)
                                                    opacity: (root.selectedTarget && root.selectedTarget.id === modelData.id) ? 1.0 : 0.72
                                                    border.color: (root.selectedTarget && root.selectedTarget.id === modelData.id) ? "#FFFFFF" : "transparent"
                                                    border.width: 2
                                                }
                                            }
                                        }

                                        // Clickable Partition / Free-Space Cards
                                        Repeater {
                                            model: modelData.segments || []
                                            delegate: Rectangle {
                                                Layout.fillWidth: true
                                                height: 54
                                                radius: 10
                                                property bool isSelected: root.selectedTarget !== null && root.selectedTarget.id === modelData.id
                                                color: isSelected ? "#26FF9933" : (modelData.selectable ? "#14FFFFFF" : "#0AFFFFFF")
                                                border.color: isSelected ? "#FF9933" : (modelData.isLocked ? "#22FFFFFF" : "#33FFFFFF")
                                                border.width: isSelected ? 2 : 1

                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 12; anchors.rightMargin: 12
                                                    spacing: 10

                                                    Rectangle {
                                                        width: 10; height: 28; radius: 5
                                                        color: root.segmentColor(modelData)
                                                    }

                                                    ColumnLayout {
                                                        spacing: 2
                                                        Layout.fillWidth: true
                                                        Text {
                                                            text: modelData.displayName + " — " + modelData.sizeLabel
                                                            color: modelData.selectable ? "#FFFFFF" : "#94A3B8"
                                                            font.pixelSize: 13; font.weight: Font.Medium
                                                        }
                                                        Text {
                                                            text: (modelData.isLocked ? "🔒 " : (modelData.recommended ? "★ " : "• "))
                                                                  + modelData.badgeText
                                                                  + (modelData.fstype && modelData.fstype !== "free" ? (" (" + modelData.fstype + ")") : "")
                                                                  + (modelData.isEsp && modelData.espFreeMib !== null && modelData.espFreeMib !== undefined ? (" · " + modelData.espFreeMib + " MiB free") : "")
                                                            color: modelData.recommended ? "#4ADE80" : (modelData.isEsp && modelData.espLowSpace ? "#FBBF24" : "#94A3B8")
                                                            font.pixelSize: 11
                                                        }
                                                    }

                                                    Text {
                                                        visible: isSelected
                                                        text: isHindi ? "चयनित ✓" : "Selected ✓"
                                                        color: "#FF9933"; font.pixelSize: 12; font.weight: Font.Bold
                                                    }
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    enabled: modelData.selectable
                                                    cursorShape: modelData.selectable ? Qt.PointingHandCursor : Qt.ForbiddenCursor
                                                    onClicked: {
                                                        root.selectedTarget = modelData
                                                        root.confirmChecked = false
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ESP Low Free Space Warning Banner (< 35 MiB)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        radius: 10
                        visible: root.selectedTarget !== null && root.selectedTarget.espLowSpace === true
                        color: "#33F59E0B"
                        border.color: "#F59E0B"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12
                            wrapMode: Text.WordWrap
                            color: "#FDE68A"; font.pixelSize: 12
                            text: root.selectedTarget
                                  ? (isHindi
                                     ? ("चेतावनी: मौजूदा EFI पार्टीशन (" + (root.selectedTarget.espPath || "") + ") में केवल " + (root.selectedTarget.espFreeMib !== null && root.selectedTarget.espFreeMib !== undefined ? root.selectedTarget.espFreeMib : "?") + " MiB खाली है (< 35 MiB)। ड्यूल-बूट बूटलोडर के लिए ~35 MiB खाली जगह ज़रूरी होती है।")
                                     : ("Warning: Preserved EFI partition (" + (root.selectedTarget.espPath || "") + ") only has " + (root.selectedTarget.espFreeMib !== null && root.selectedTarget.espFreeMib !== undefined ? root.selectedTarget.espFreeMib : "?") + " MiB free (< 35 MiB recommended). Dual-boot bootloader entries may fail if EFI runs full."))
                                  : ""
                        }
                    }
                }

                // =============================================================
                // SCREEN 2: Review & Explicit Confirmation
                // =============================================================
                ColumnLayout {
                    spacing: 16

                    Text {
                        text: isHindi ? "इंस्टॉलेशन सारांश व पुष्टि" : "Review & Confirm Installation"
                        color: "#FFFFFF"; font.pixelSize: 28; font.weight: Font.Bold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 220
                        radius: 16
                        color: "#14FFFFFF"
                        border.color: "#2EFFFFFF"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 10

                            Text {
                                text: isHindi ? "लक्ष्य स्थान (Install Target):" : "Target Storage Slot:"
                                color: "#94A3B8"; font.pixelSize: 12
                            }
                            Text {
                                text: root.selectedTarget ? (root.selectedTarget.displayName + " (" + root.selectedTarget.sizeLabel + ")") : "-"
                                color: "#FFFFFF"; font.pixelSize: 18; font.weight: Font.Bold
                            }
                            Text {
                                text: root.selectedTarget && root.selectedTarget.kind === "partition"
                                      ? (isHindi ? "• मोड: केवल चुना हुआ सिंगल पार्टीशन Btrfs में रीक्लेम होगा (clearpart --none, अन्य सभी पार्टीशन सुरक्षित)।" : "• Mode: Reclaim ONLY this single partition as Btrfs (root, var, home). All neighboring partitions untouched.")
                                      : (isHindi ? "• मोड: खाली जगह (Unallocated) में 1 GB /boot + Btrfs (root, var, home) बनेगा। Windows व अन्य डेटा सुरक्षित रहेंगे।" : "• Mode: Automatic 1 GB ext4 /boot + Btrfs (root, var, home) in Unallocated space. All existing OS partitions preserved.")
                                color: "#CBD5E1"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                            }
                            Text {
                                text: root.selectedTarget && root.selectedTarget.espPath
                                      ? ("• EFI System Partition: " + root.selectedTarget.espPath + " (--noformat · Windows Boot Manager preserved)")
                                      : "• EFI System Partition: New 512 MB FAT32 EFI partition will be created"
                                color: "#38BDF8"; font.pixelSize: 13
                            }
                            Text {
                                text: isHindi
                                      ? "• रीबूट के बाद: Stage 2 Kushagra Setup Wizard (kushagra-setup) आपका यूज़र अकाउंट बनाएगा।"
                                      : "• Post-Install Handoff: System boots directly into kushagra-setup (OOBE) to create your admin user."
                                color: "#4ADE80"; font.pixelSize: 13
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        radius: 12
                        visible: root.selectedTarget !== null && root.selectedTarget.kind === "partition"
                        color: "#28EF4444"
                        border.color: "#EF4444"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 14
                            color: "#FCA5A5"; font.pixelSize: 12; wrapMode: Text.WordWrap
                            text: root.selectedTarget
                                  ? (isHindi
                                     ? ("चेतावनी: केवल " + (root.selectedTarget.partPath || "") + " पर मौजूद डेटा मिटाकर Btrfs बनाया जाएगा। Windows NTFS व EFI नहीं छेड़े जाएंगे।")
                                     : ("Caution: Only " + (root.selectedTarget.partPath || "") + " will be formatted for Kushagra OS. Windows NTFS and EFI remain untouched."))
                                  : ""
                        }
                    }

                    GlassCheckBox {
                        id: confirmBox
                        Layout.fillWidth: true
                        checked: root.confirmChecked
                        text: root.selectedTarget && root.selectedTarget.kind === "partition"
                              ? (isHindi ? ("मैं पुष्टि करता हूँ कि केवल " + (root.selectedTarget.partPath || "") + " फॉर्मेट हो और इंस्टॉलेशन शुरू हो।") : ("I confirm formatting ONLY " + (root.selectedTarget.partPath || "") + " while preserving all other partitions."))
                              : (isHindi ? "मैं जांच किए गए खाली स्थान पर Kushagra OS इंस्टॉल करने की पुष्टि करता हूँ।" : "I confirm installing Kushagra OS into the selected unallocated free space.")
                        onToggled: root.confirmChecked = checked
                    }

                    Item { Layout.fillHeight: true }
                }

                // =============================================================
                // SCREEN 3: Live Progress + Expandable Log Drawer
                // =============================================================
                ColumnLayout {
                    spacing: 14

                    Text {
                        text: installerBackend.installSucceeded
                              ? (isHindi ? "✓ इंस्टॉलेशन सफलतापूर्वक पूरा हुआ!" : "✓ Kushagra OS Installed Successfully!")
                              : (installerBackend.installError.length > 0
                                 ? (isHindi ? "इंस्टॉलेशन में त्रुटि आई" : "Installation Encountered an Error")
                                 : (isHindi ? "Kushagra OS इंस्टॉल हो रहा है..." : "Installing Kushagra OS..."))
                        color: installerBackend.installSucceeded ? "#4ADE80" : (installerBackend.installError.length > 0 ? "#F87171" : "#FFFFFF")
                        font.pixelSize: 26; font.weight: Font.Bold
                    }

                    Text {
                        text: installerBackend.installStage.length > 0 ? installerBackend.installStage : "..."
                        color: "#CBD5E1"; font.pixelSize: 14; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }

                    // Progress Bar
                    Rectangle {
                        Layout.fillWidth: true
                        height: 18
                        radius: 9
                        color: "#1E293B"
                        border.color: "#33FFFFFF"

                        Rectangle {
                            height: parent.height
                            radius: 9
                            width: Math.max(18, Math.round(parent.width * (installerBackend.installPercent / 100.0)))
                            color: installerBackend.installError.length > 0 ? "#EF4444" : (installerBackend.installSucceeded ? "#22C55E" : "#FF9933")
                            Behavior on width { NumberAnimation { duration: 250 } }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: installerBackend.installPercent + "%"
                            color: "#94A3B8"; font.pixelSize: 13; font.weight: Font.Bold
                        }
                        Item { Layout.fillWidth: true }
                        GlassButton {
                            text: root.logsExpanded
                                  ? (isHindi ? "लॉग छुपाएं ▲" : "Hide Installation Logs ▲")
                                  : (isHindi ? "इंस्टॉलेशन लॉग देखें ▼" : "View Installation Logs ▼")
                            onClicked: root.logsExpanded = !root.logsExpanded
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        radius: 10
                        visible: installerBackend.installError.length > 0
                        color: "#33EF4444"
                        border.color: "#EF4444"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12
                            color: "#FCA5A5"; font.pixelSize: 12; wrapMode: Text.WordWrap
                            text: installerBackend.installError
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.logsExpanded
                        radius: 10
                        color: "#0A0F1E"
                        border.color: "#33FFFFFF"

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 8
                            TextArea {
                                readOnly: true
                                text: installerBackend.installLogsText
                                color: "#CBD5E1"
                                font.family: "monospace"
                                font.pixelSize: 11
                                wrapMode: TextEdit.Wrap
                                background: Item {}
                            }
                        }
                    }

                    Item { Layout.fillHeight: true; visible: !root.logsExpanded }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1FFFFFFF" }

            // Bottom Navigation Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                GlassButton {
                    visible: (root.currentStep === 1 || root.currentStep === 2) && !installerBackend.installing
                    text: isHindi ? "← पीछे" : "← Back"
                    onClicked: root.currentStep -= 1
                }

                GlassButton {
                    visible: root.currentStep === 3 && installerBackend.installError.length > 0 && !installerBackend.installing
                    text: isHindi ? "← वापस ड्राइव चुनें" : "← Return to Target Selection"
                    onClicked: root.currentStep = 1
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    visible: root.currentStep === 1
                    highlighted: true
                    enabled: root.selectedTarget !== null && !installerBackend.scanning
                    text: isHindi ? "आगे बढ़ें →" : "Next →"
                    onClicked: root.currentStep = 2
                }

                GlassButton {
                    visible: root.currentStep === 2
                    highlighted: true
                    enabled: root.selectedTarget !== null && root.confirmChecked
                    text: isHindi ? "इंस्टॉल शुरू करें ✓" : "Install Kushagra OS ✓"
                    onClicked: {
                        if (!root.selectedTarget) return
                        root.currentStep = 3
                        installerBackend.startInstall(root.selectedTarget.id)
                    }
                }

                GlassButton {
                    visible: root.currentStep === 3 && installerBackend.installSucceeded
                    enabled: !installerBackend.launchingDesktop
                    text: isHindi ? "लाइव डेस्कटॉप पर जाएं" : "Continue Live Desktop"
                    onClicked: installerBackend.tryLiveDesktop()
                }

                GlassButton {
                    visible: root.currentStep === 3 && installerBackend.installSucceeded
                    enabled: !installerBackend.launchingDesktop
                    highlighted: true
                    text: isHindi ? "अभी रीस्टार्ट करें ↻" : "Restart System Now ↻"
                    onClicked: installerBackend.rebootNow()
                }
            }
        }

        // Crisp non-blocking loading state while LiveCD Plasma desktop & panel start underneath
        Rectangle {
            anchors.fill: parent
            radius: 24
            z: 20
            visible: installerBackend.launchingDesktop
            color: "#D9060913"

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
            }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 64, 400)
                height: launchOverlayCol.implicitHeight + 48
                radius: 18
                color: "#F00F172A"
                border.color: "#44FF9933"
                border.width: 1

                ColumnLayout {
                    id: launchOverlayCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 24
                    spacing: 14

                    Rectangle {
                        width: 34
                        height: 34
                        radius: 17
                        color: "transparent"
                        border.width: 3
                        border.color: "#33FF9933"
                        Layout.alignment: Qt.AlignHCenter

                        Rectangle {
                            width: 10
                            height: 10
                            radius: 5
                            color: "#FF9933"
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: -3
                        }

                        RotationAnimation on rotation {
                            from: 0
                            to: 360
                            duration: 1000
                            loops: Animation.Infinite
                            running: installerBackend.launchingDesktop
                        }
                    }

                    Text {
                        text: isHindi ? "लाइव डेस्कटॉप खुल रहा है..." : "Opening Live Desktop..."
                        color: "#FFFFFF"
                        font.pixelSize: 17
                        font.weight: Font.Bold
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Text {
                        text: isHindi
                              ? "कृपया प्रतीक्षा करें, KDE Plasma डेस्कटॉप और पैनल तैयार हो रहे हैं..."
                              : "Starting KDE Plasma desktop & taskbar seamlessly..."
                        color: "#94A3B8"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }
}
