class LimpiaDefensa < Formula
  desc "Secure system optimizer and malware scanner for macOS"
  homepage "https://github.com/XavaATI/limpia-defensa"
  url "https://github.com/XavaATI/limpia-defensa/releases/download/v1.4.1/limpia-defensa-v1.4.1.tar.gz"
  sha256 "63db90945eed62128f1f36dd408bdc9cf4d2ef60cec31c93161b6297fe310127"
  license "MIT"

  depends_on "python@3"

  def install
    # Install CLI engine
    bin.install "scripts/limpia_defensa.py" => "limpia-defensa-cli"
    bin.install_symlink "#{bin}/limpia-defensa-cli" => "limpia-defensa"

    # Install Solo-Operator Release Pipeline
    bin.install "scripts/release_pipeline.py" => "limpia-defensa-release"

    # Install GUI binary (compiled & signed)
    bin.install "scripts/limpia-defensa-gui"

    # Install LaunchAgent template, Store Catalog, Source & Test Suites
    (prefix/"scripts").install "scripts/limpia_defensa.py"
    (prefix/"scripts").install "scripts/release_pipeline.py"
    (prefix/"scripts").install "scripts/LimpiaDefensaGUI.swift"
    (prefix/"scripts").install "scripts/com.limpiadefensa.agent.plist"
    (prefix/"scripts").install "scripts/store_catalog.json"
    (prefix/"scripts").install "scripts/kali_test_suite.py"
    (prefix/"scripts").install "scripts/verify_truth_and_excellence.py"
  end

  def caveats
    <<~EOS
      Limpia-Defensa installed successfully!

      To run the system health and environment doctor:
        limpia-defensa doctor

      To deploy and start the background API daemon automatically:
        limpia-defensa install-daemon --port 8989

      To launch the native macOS GUI:
        limpia-defensa-gui

      To build and certify a release patch:
        limpia-defensa-release --bump patch
    EOS
  end

  test do
    system "#{bin}/limpia-defensa", "--help"
  end
end
