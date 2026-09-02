class LimpiaDefensa < Formula
  desc "Secure system optimizer and malware scanner for macOS"
  homepage "https://github.com/XavaATI/limpia-defensa"
  url "https://github.com/XavaATI/limpia-defensa/releases/download/v1.4.3/limpia-defensa-v1.4.3.tar.gz"
  sha256 "5cba6270c17cb0b8f068ee92ce33f925f489a017aceec644092df74268ff9244"
  license "MIT"

  depends_on "python@3"

  def install
    # Install all scripts, store catalog, plist, and test suites into prefix/scripts
    (prefix/"scripts").install Dir["scripts/*"]

    # Install executable symlinks into bin
    bin.install_symlink "#{prefix}/scripts/limpia_defensa.py" => "limpia-defensa-cli"
    bin.install_symlink "#{bin}/limpia-defensa-cli" => "limpia-defensa"
    bin.install_symlink "#{prefix}/scripts/release_pipeline.py" => "limpia-defensa-release"
    bin.install_symlink "#{prefix}/scripts/limpia-defensa-gui" => "limpia-defensa-gui"
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
