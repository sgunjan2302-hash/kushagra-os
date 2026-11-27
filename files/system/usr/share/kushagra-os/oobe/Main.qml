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
    title: "Kushagra OS Setup"

    property int currentStep: 0 // 0=Welcome, 1=Network, 2=Workspace, 3=Account
    property string selectedLanguage: "en_IN" // "en_IN" | "hi_IN"
    property string selectedWorkspace: "classic" // "classic" | "floating"
    property string selectedSsid: ""
    property bool selectedSsidSecured: false
    property bool usernameManuallyEdited: false
    property bool showPassword: false
    property bool setupDoneBanner: false
    property bool isHindi: selectedLanguage === "hi_IN"

    onCurrentStepChanged: {
        if (currentStep === 3) {
            fullNameField.forceActiveFocus()
        }
    }

    palette.windowText: "#FFFFFF"
    palette.text: "#FFFFFF"
    palette.buttonText: "#FFFFFF"
    palette.button: "#1E293B"

    component GlassCheckBox: CheckBox {
        id: cbControl
        implicitHeight: 32
        spacing: 10
        hoverEnabled: true
        indicator: Rectangle {
            implicitWidth: 20
            implicitHeight: 20
            x: cbControl.leftPadding
            y: parent.height / 2 - height / 2
            radius: 5
            color: cbControl.checked ? "#FF9933" : (cbControl.hovered ? "#28FFFFFF" : "#1AFFFFFF")
            border.color: cbControl.checked ? "#FF9933" : (cbControl.activeFocus ? "#FF9933" : "#66FFFFFF")
            border.width: 1.5
            Text {
                anchors.centerIn: parent
                visible: cbControl.checked
                text: "✓"
                color: "#060913"
                font.pixelSize: 13
                font.weight: Font.Bold
            }
        }
        contentItem: Text {
            text: cbControl.text
            font.pixelSize: 13
            color: cbControl.enabled ? "#FFFFFF" : "#64748B"
            verticalAlignment: Text.AlignVCenter
            leftPadding: cbControl.indicator.width + cbControl.spacing
        }
    }

    component GlassSwitch: Switch {
        id: swControl
        implicitHeight: 32
        spacing: 10
        hoverEnabled: true
        indicator: Rectangle {
            implicitWidth: 44
            implicitHeight: 24
            x: swControl.leftPadding
            y: parent.height / 2 - height / 2
            radius: 12
            color: swControl.checked ? "#FF9933" : (swControl.hovered ? "#2EFFFFFF" : "#1E293B")
            border.color: swControl.checked ? "#FF9933" : (swControl.activeFocus ? "#FF9933" : "#64748B")
            border.width: 1

            Rectangle {
                x: swControl.checked ? parent.width - width - 3 : 3
                anchors.verticalCenter: parent.verticalCenter
                width: 18
                height: 18
                radius: 9
                color: swControl.checked ? "#060913" : "#E2E8F0"
                Behavior on x { NumberAnimation { duration: 140 } }
            }
        }
        contentItem: Text {
            text: swControl.text
            font.pixelSize: 13
            color: swControl.enabled ? "#FFFFFF" : "#64748B"
            verticalAlignment: Text.AlignVCenter
            leftPadding: swControl.indicator.width + swControl.spacing
        }
    }

    component GlassButton: Button {
        id: btnControl
        implicitHeight: 38
        leftPadding: 18
        rightPadding: 18
        topPadding: 8
        bottomPadding: 8
        hoverEnabled: true
        background: Rectangle {
            implicitWidth: 88
            implicitHeight: 38
            radius: 10
            color: {
                if (!btnControl.enabled) {
                    return btnControl.highlighted ? "#33FF9933" : "#10FFFFFF"
                }
                if (btnControl.highlighted) {
                    return btnControl.down ? "#D97706" : (btnControl.hovered ? "#FFA94D" : "#FF9933")
                }
                return btnControl.down ? "#33FFFFFF" : (btnControl.hovered ? "#24FFFFFF" : "#16FFFFFF")
            }
            border.color: {
                if (!btnControl.enabled) return "#22FFFFFF"
                if (btnControl.highlighted) return btnControl.activeFocus ? "#FFFFFF" : "#FF9933"
                return btnControl.activeFocus ? "#FF9933" : "#38FFFFFF"
            }
            border.width: 1
        }
        contentItem: Text {
            text: btnControl.text
            font.pixelSize: 13
            font.weight: btnControl.highlighted ? Font.Bold : Font.Medium
            color: {
                if (!btnControl.enabled) return "#94A3B8"
                return btnControl.highlighted ? "#060913" : "#FFFFFF"
            }
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    Connections {
        target: oobeBackend
        function onSetupCompleted() {
            root.setupDoneBanner = true
        }
    }

    // Ambient dark-glass backdrop with Indian Saffron & Emerald radial accents
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#060913" }
            GradientStop { position: 0.55; color: "#0C1528" }
            GradientStop { position: 1.0; color: "#08121A" }
        }

        Rectangle {
            width: 560; height: 560; radius: 280
            x: -140; y: -160
            color: "#18FF9933"
        }

        Rectangle {
            width: 520; height: 520; radius: 260
            x: parent.width - 360; y: parent.height - 340
            color: "#14138808"
        }
    }

    // Center Frosted Dark-Glass Card
    Rectangle {
        id: glassCard
        anchors.centerIn: parent
        width: Math.min(parent.width - 96, 860)
        height: Math.min(parent.height - 80, 620)
        radius: 24
        color: "#CC0F172A"
        border.color: "#2EFFFFFF"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 36
            spacing: 20

            // Top Brand Header + Step Indicator Pills
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
                        text: "KUSHAGRA OS"
                        color: "#FFFFFF"
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        font.letterSpacing: 1.8
                    }
                    Text {
                        text: isHindi ? "फ़ेडोरा एटॉमिक 44 · अपरिवर्तनीय डेस्कटॉप" : "FEDORA ATOMIC 44 · IMMUTABLE DESKTOP"
                        color: "#94A3B8"
                        font.pixelSize: 11
                        font.letterSpacing: 1.2
                    }
                }

                Item { Layout.fillWidth: true }

                Row {
                    spacing: 8
                    Repeater {
                        model: 4
                        Rectangle {
                            width: index === root.currentStep ? 30 : 10
                            height: 8
                            radius: 4
                            color: index === root.currentStep ? "#FF9933" : (index < root.currentStep ? "#138808" : "#33FFFFFF")
                            Behavior on width { NumberAnimation { duration: 180 } }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1FFFFFFF" }

            // Dynamic Step Viewport
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: Math.min(3, Math.max(0, root.currentStep))

                // =============================================================
                // SCREEN 1: Welcome & Language
                // =============================================================
                ColumnLayout {
                    spacing: 18

                    Text {
                        text: isHindi ? "कुशाग्र ओएस में आपका स्वागत है" : "Welcome to Kushagra OS"
                        color: "#FFFFFF"
                        font.pixelSize: 30
                        font.weight: Font.Bold
                    }

                    Text {
                        text: isHindi
                              ? "अपनी पसंदीदा भाषा चुनें। Fcitx5 हिंदी टाइपिंग और स्मार्ट कीबोर्ड पहले से तैयार हैं।"
                              : "Choose your primary language. Native Indic typing via Fcitx5 (Wayland) is built in."
                        color: "#CBD5E1"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 10
                        spacing: 16

                        // English (India) Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 150
                            radius: 16
                            color: root.selectedLanguage === "en_IN" ? "#24FF9933" : "#12FFFFFF"
                            border.color: root.selectedLanguage === "en_IN" ? "#FF9933" : "#26FFFFFF"
                            border.width: root.selectedLanguage === "en_IN" ? 2 : 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 8
                                Text { text: "EN (IN)"; color: "#FF9933"; font.pixelSize: 13; font.weight: Font.Bold }
                                Text { text: "English (India)"; color: "#FFFFFF"; font.pixelSize: 20; font.weight: Font.Bold }
                                Text {
                                    text: "Default system UI in English with Rupee, IST timezone & optional Hindi phonetic typing."
                                    color: "#94A3B8"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedLanguage = "en_IN"
                            }
                        }

                        // Hindi (India) Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 150
                            radius: 16
                            color: root.selectedLanguage === "hi_IN" ? "#24FF9933" : "#12FFFFFF"
                            border.color: root.selectedLanguage === "hi_IN" ? "#FF9933" : "#26FFFFFF"
                            border.width: root.selectedLanguage === "hi_IN" ? 2 : 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 8
                                Text { text: "हिन्दी (भारत)"; color: "#22C55E"; font.pixelSize: 13; font.weight: Font.Bold }
                                Text { text: "हिन्दी · Fcitx5 Inscript / ITRANS"; color: "#FFFFFF"; font.pixelSize: 20; font.weight: Font.Bold }
                                Text {
                                    text: "हिंदी सिस्टम लोकल (hi_IN.UTF-8) और Fcitx5 Devanagari इनपुट सक्रिय।"
                                    color: "#94A3B8"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedLanguage = "hi_IN"
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 54
                        radius: 12
                        color: "#12138808"
                        border.color: "#4422C55E"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 16
                            text: isHindi
                                  ? "✓ Fcitx5 Wayland + ZRAM (zstd) + Atomic Rollback सुरक्षा सक्रिय"
                                  : "✓ Fcitx5 Wayland Indic IME + ZRAM (zstd) + Atomic Rollback protection ready"
                            color: "#86EFAC"
                            font.pixelSize: 13
                        }
                    }

                    Item { Layout.fillHeight: true }
                }

                // =============================================================
                // SCREEN 2: Network (Optional Wi-Fi via nmcli)
                // =============================================================
                ColumnLayout {
                    spacing: 14

                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            spacing: 4
                            Text {
                                text: isHindi ? "इंटरनेट से जुड़ें (वैकल्पिक)" : "Connect to Wi-Fi (Optional)"
                                color: "#FFFFFF"; font.pixelSize: 26; font.weight: Font.Bold
                            }
                            Text {
                                text: (oobeBackend && oobeBackend.wifiStatus.length > 0)
                                      ? oobeBackend.wifiStatus
                                      : (isHindi ? "आप इंटरनेट के बिना भी सेटअप पूरा कर सकते हैं।" : "Connect to Wi-Fi via NetworkManager or skip to finish setup offline.")
                                color: "#94A3B8"; font.pixelSize: 13
                            }
                        }
                        Item { Layout.fillWidth: true }
                        GlassButton {
                            text: (oobeBackend && oobeBackend.wifiBusy) ? (isHindi ? "स्कैन..." : "Scanning...") : (isHindi ? "रीफ्रेश" : "Refresh")
                            enabled: Boolean(oobeBackend && !oobeBackend.wifiBusy)
                            onClicked: if (oobeBackend) oobeBackend.scanWifi()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 14
                        color: "#10FFFFFF"
                        border.color: "#22FFFFFF"
                        clip: true

                        ListView {
                            id: wifiListView
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6
                            model: oobeBackend ? oobeBackend.wifiList : []

                            delegate: Rectangle {
                                width: wifiListView.width
                                height: 48
                                radius: 10
                                color: modelData.ssid === root.selectedSsid ? "#26FF9933" : (modelData.connected ? "#1E138808" : "#12FFFFFF")
                                border.color: modelData.ssid === root.selectedSsid ? "#FF9933" : "transparent"

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    Text {
                                        text: modelData.ssid
                                        color: "#FFFFFF"; font.pixelSize: 14; font.weight: Font.Medium
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.connected ? (isHindi ? "कनेक्टेड" : "Connected") : modelData.security
                                        color: modelData.connected ? "#4ADE80" : "#94A3B8"
                                        font.pixelSize: 12
                                    }
                                    Text {
                                        text: modelData.signal + "%"
                                        color: "#CBD5E1"; font.pixelSize: 12; font.weight: Font.Bold
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.selectedSsid = modelData.ssid
                                        root.selectedSsidSecured = modelData.secured
                                        if (!modelData.secured && oobeBackend) {
                                            oobeBackend.connectWifi(modelData.ssid, "")
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: Boolean(oobeBackend && oobeBackend.wifiList.length === 0 && !oobeBackend.wifiBusy)
                            text: isHindi
                                  ? "कोई Wi-Fi नेटवर्क नहीं मिला (Ethernet पहले से जुड़ा हो सकता है या बिना नेटवर्क आगे बढ़ें)"
                                  : "No Wi-Fi networks found (Ethernet may already be connected, or click Skip for now)."
                            color: "#94A3B8"; font.pixelSize: 13
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.selectedSsid.length > 0 && root.selectedSsidSecured
                        spacing: 10
                        TextField {
                            id: wifiPasswordField
                            Layout.fillWidth: true
                            placeholderText: isHindi ? (root.selectedSsid + " का पासवर्ड डालें") : ("Enter password for " + root.selectedSsid)
                            placeholderTextColor: "#64748B"
                            echoMode: TextInput.Password
                            color: "#FFFFFF"
                            background: Rectangle {
                                radius: 8
                                color: "#1AFFFFFF"
                                border.color: wifiPasswordField.activeFocus ? "#FF9933" : "#33FFFFFF"
                                border.width: 1
                            }
                        }
                        GlassButton {
                            text: isHindi ? "कनेक्ट करें" : "Connect"
                            enabled: Boolean(oobeBackend && !oobeBackend.wifiBusy)
                            onClicked: if (oobeBackend) oobeBackend.connectWifi(root.selectedSsid, wifiPasswordField.text)
                        }
                    }
                }

                // =============================================================
                // SCREEN 3: Choose Your Workspace Style
                // =============================================================
                ColumnLayout {
                    spacing: 18

                    Text {
                        text: isHindi ? "अपना डेस्कटॉप स्टाइल चुनें" : "Choose Your Workspace Style"
                        color: "#FFFFFF"; font.pixelSize: 28; font.weight: Font.Bold
                    }
                    Text {
                        text: isHindi
                              ? "बाद में आप कभी भी 'ujust switch-layout' से इसे बदल सकते हैं।"
                              : "Pick the desktop layout you feel most at home in. You can switch anytime via 'ujust switch-layout'."
                        color: "#CBD5E1"; font.pixelSize: 14
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 20

                        // Familiar Mode (Windows-style Bottom Taskbar)
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 18
                            color: root.selectedWorkspace === "classic" ? "#22FF9933" : "#10FFFFFF"
                            border.color: root.selectedWorkspace === "classic" ? "#FF9933" : "#28FFFFFF"
                            border.width: root.selectedWorkspace === "classic" ? 2 : 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14

                                // Visual Mock Desktop Preview (Windows Taskbar)
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 150
                                    radius: 12
                                    color: "#0A1224"
                                    border.color: "#33FFFFFF"

                                    Rectangle {
                                        anchors.centerIn: parent
                                        anchors.verticalCenterOffset: -12
                                        width: 140; height: 82; radius: 8
                                        color: "#1E293B"; border.color: "#475569"
                                    }
                                    Rectangle {
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                                        height: 24; radius: 4
                                        color: "#E61E293B"
                                        Row {
                                            anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                            Rectangle { width: 12; height: 12; radius: 3; color: "#FF9933" }
                                            Rectangle { width: 28; height: 8; radius: 2; color: "#94A3B8" }
                                            Rectangle { width: 28; height: 8; radius: 2; color: "#64748B" }
                                        }
                                    }
                                }

                                Text {
                                    text: isHindi ? "फ़ैमिलियर मोड (Familiar Mode)" : "Familiar Mode"
                                    color: "#FFFFFF"; font.pixelSize: 20; font.weight: Font.Bold
                                }
                                Text {
                                    text: isHindi
                                          ? "Windows जैसा पारंपरिक बॉटम टास्कबार, स्टार्ट मेन्यू और सिस्टम ट्रे।"
                                          : "Classic bottom taskbar, full-width launcher, and familiar system tray workflows."
                                    color: "#94A3B8"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                                Item { Layout.fillHeight: true }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedWorkspace = "classic"
                            }
                        }

                        // Studio Mode (macOS Top Bar + Floating Dock)
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 18
                            color: root.selectedWorkspace === "floating" ? "#22FF9933" : "#10FFFFFF"
                            border.color: root.selectedWorkspace === "floating" ? "#FF9933" : "#28FFFFFF"
                            border.width: root.selectedWorkspace === "floating" ? 2 : 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14

                                // Visual Mock Desktop Preview (macOS Top Bar + Floating Dock)
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 150
                                    radius: 12
                                    color: "#0A1224"
                                    border.color: "#33FFFFFF"

                                    Rectangle {
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                                        height: 18; radius: 4
                                        color: "#E61E293B"
                                        Rectangle { anchors.centerIn: parent; width: 42; height: 6; radius: 3; color: "#CBD5E1" }
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 140; height: 74; radius: 8
                                        color: "#1E293B"; border.color: "#475569"
                                    }
                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.bottom: parent.bottom; anchors.bottomMargin: 8
                                        width: 124; height: 22; radius: 11
                                        color: "#E6334155"; border.color: "#55FFFFFF"
                                        Row {
                                            anchors.centerIn: parent; spacing: 8
                                            Rectangle { width: 12; height: 12; radius: 4; color: "#FF9933" }
                                            Rectangle { width: 12; height: 12; radius: 4; color: "#38BDF8" }
                                            Rectangle { width: 12; height: 12; radius: 4; color: "#22C55E" }
                                            Rectangle { width: 12; height: 12; radius: 4; color: "#A855F7" }
                                        }
                                    }
                                }

                                Text {
                                    text: isHindi ? "स्टूडियो मोड (Studio Mode)" : "Studio Mode"
                                    color: "#FFFFFF"; font.pixelSize: 20; font.weight: Font.Bold
                                }
                                Text {
                                    text: isHindi
                                          ? "macOS जैसा स्लिम टॉप बार और स्मार्ट ऑटो-हाइड फ़्लोटिंग डॉक।"
                                          : "Slim global top status bar with centered floating auto-dodge dock."
                                    color: "#94A3B8"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                                Item { Layout.fillHeight: true }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedWorkspace = "floating"
                            }
                        }
                    }
                }

                // =============================================================
                // SCREEN 4: Create Your Account
                // =============================================================
                ColumnLayout {
                    spacing: 14

                    Text {
                        text: isHindi ? "अपना अकाउंट बनाएं" : "Create Your Account"
                        color: "#FFFFFF"; font.pixelSize: 28; font.weight: Font.Bold
                    }
                    Text {
                        text: isHindi
                              ? "यह सिस्टम एडमिनिस्ट्रेटर (wheel) अकाउंट होगा। सेटअप के बाद कोई असुरक्षित डिफ़ॉल्ट पासवर्ड नहीं बचेगा।"
                              : "Creates your primary administrator (wheel) account and seals first-boot setup."
                        color: "#CBD5E1"; font.pixelSize: 13
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: isHindi ? "पूरा नाम (Full Name)" : "Full Name"; color: "#CBD5E1"; font.pixelSize: 12 }
                            TextField {
                                id: fullNameField
                                Layout.fillWidth: true
                                placeholderText: "e.g. Kushagra Sharma"
                                placeholderTextColor: "#64748B"
                                color: "#FFFFFF"
                                background: Rectangle {
                                    radius: 8
                                    color: "#1AFFFFFF"
                                    border.color: fullNameField.activeFocus ? "#FF9933" : "#33FFFFFF"
                                    border.width: 1
                                }
                                onTextChanged: {
                                    if (!root.usernameManuallyEdited && oobeBackend) {
                                        usernameField.text = oobeBackend.suggestUsername(text)
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: isHindi ? "यूज़रनेम (Username)" : "Username"; color: "#CBD5E1"; font.pixelSize: 12 }
                            TextField {
                                id: usernameField
                                Layout.fillWidth: true
                                placeholderText: "e.g. kushagra"
                                placeholderTextColor: "#64748B"
                                color: "#FFFFFF"
                                background: Rectangle {
                                    radius: 8
                                    color: "#1AFFFFFF"
                                    border.color: usernameField.activeFocus ? "#FF9933" : "#33FFFFFF"
                                    border.width: 1
                                }
                                onTextEdited: root.usernameManuallyEdited = true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: isHindi ? "पासवर्ड (कम से कम 4 अक्षर)" : "Password (min 4 chars)"; color: "#CBD5E1"; font.pixelSize: 12 }
                            TextField {
                                id: passwordField
                                Layout.fillWidth: true
                                echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                                color: "#FFFFFF"
                                background: Rectangle {
                                    radius: 8
                                    color: "#1AFFFFFF"
                                    border.color: passwordField.activeFocus ? "#FF9933" : "#33FFFFFF"
                                    border.width: 1
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: isHindi ? "पासवर्ड दोहराएं" : "Confirm Password"; color: "#CBD5E1"; font.pixelSize: 12 }
                            TextField {
                                id: confirmField
                                Layout.fillWidth: true
                                echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                                color: "#FFFFFF"
                                background: Rectangle {
                                    radius: 8
                                    color: "#1AFFFFFF"
                                    border.color: confirmField.activeFocus ? "#FF9933" : "#33FFFFFF"
                                    border.width: 1
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 24
                        GlassCheckBox {
                            checked: root.showPassword
                            text: isHindi ? "पासवर्ड दिखाएं" : "Show password"
                            onToggled: root.showPassword = checked
                        }
                        Item { Layout.fillWidth: true }
                        GlassSwitch {
                            id: autoLoginSwitch
                            checked: true
                            text: isHindi ? "बूट पर ऑटो-लॉगिन चालू रखें" : "Auto-login on boot"
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        radius: 10
                        visible: Boolean(oobeBackend && oobeBackend.setupError.length > 0) || (confirmField.text.length > 0 && confirmField.text !== passwordField.text)
                        color: "#33EF4444"
                        border.color: "#EF4444"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left; anchors.leftMargin: 12
                            color: "#FCA5A5"; font.pixelSize: 12
                            text: (oobeBackend && oobeBackend.setupError.length > 0)
                                  ? oobeBackend.setupError
                                  : (isHindi ? "दोनों पासवर्ड मेल नहीं खा रहे हैं।" : "Passwords do not match.")
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: Boolean(oobeBackend && oobeBackend.applyBusy) || root.setupDoneBanner
                        spacing: 12
                        BusyIndicator { running: true; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
                        Text {
                            text: root.setupDoneBanner
                                  ? (isHindi ? "✓ सेटअप पूरा हुआ! आपका Kushagra OS डेस्कटॉप शुरू हो रहा है..." : "✓ Setup complete! Transitioning into your Kushagra OS desktop...")
                                  : (isHindi ? "आपका अकाउंट और डेस्कटॉप तैयार किया जा रहा है..." : "Creating account & preparing your Plasma 6 desktop...")
                            color: root.setupDoneBanner ? "#4ADE80" : "#FF9933"
                            font.pixelSize: 14
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1FFFFFFF" }

            // Bottom Navigation Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                GlassButton {
                    visible: root.currentStep > 0 && !(oobeBackend && oobeBackend.applyBusy) && !root.setupDoneBanner
                    focusPolicy: Qt.NoFocus
                    text: isHindi ? "← पीछे" : "← Back"
                    onClicked: if (root.currentStep > 0) root.currentStep -= 1
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    visible: root.currentStep === 1 && !(oobeBackend && oobeBackend.applyBusy)
                    text: isHindi ? "अभी छोड़ें (Skip)" : "Skip for now"
                    onClicked: root.currentStep = 2
                }

                GlassButton {
                    visible: root.currentStep < 3
                    enabled: root.currentStep < 3
                    focusPolicy: Qt.NoFocus
                    text: isHindi ? "आगे बढ़ें →" : "Continue →"
                    highlighted: true
                    onClicked: {
                        if (root.currentStep < 3) {
                            root.currentStep += 1
                            if (root.currentStep === 1 && oobeBackend && oobeBackend.wifiList.length === 0) {
                                oobeBackend.scanWifi()
                            }
                        }
                    }
                }

                GlassButton {
                    visible: root.currentStep === 3
                    highlighted: true
                    enabled: Boolean(oobeBackend && !oobeBackend.applyBusy) && !root.setupDoneBanner && passwordField.text.length >= 4 && passwordField.text === confirmField.text && usernameField.text.trim().length > 0
                    text: isHindi ? "सेटअप पूरा करें ✓" : "Complete Setup ✓"
                    onClicked: {
                        if (oobeBackend) {
                            oobeBackend.finishSetup(
                                fullNameField.text,
                                usernameField.text,
                                passwordField.text,
                                autoLoginSwitch.checked,
                                root.selectedWorkspace,
                                root.selectedLanguage
                            )
                        }
                    }
                }
            }
        }
    }
}
