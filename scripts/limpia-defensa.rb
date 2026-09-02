class LimpiaDefensa < Formula
  desc "Secure system optimizer and malware scanner for macOS"
  homepage "https://github.com/XavaATI/limpia-defensa"
  url "https://github.com/XavaATI/limpia-defensa/releases/download/v1.4.2/limpia-defensa-v1.4.2.tar.gz"
  sha256 "c48a2e8cf077c4972967c3205bfd9e2dc49617e7ba2d86b244f74008a889fa26"
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
