class LimpiaDefensa < Formula
  desc "✊ Secure system optimizer and malware scanner for macOS"
  homepage "https://github.com/xavasena/limpia-defensa"
  url "https://github.com/xavasena/limpia-defensa/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # Placeholder SHA-256 for release tarball
  license "MIT"

  depends_on "python@3"

  def install
    # Install CLI engine
    bin.install "scripts/limpia_defensa.py" => "limpia-defensa-cli"
    
    # Install GUI binary (compiled & signed)
    bin.install "scripts/limpia-defensa-gui"

    # Install LaunchAgent template
    (prefix/"scripts").install "scripts/com.limpiadefensa.agent.plist"
  end

  def post_install
    # Deploy agent plist to user launchd environment
    agent_path = File.expand_path("~/Library/LaunchAgents/com.limpiadefensa.agent.plist")
    source_plist = "#{opt_prefix}/scripts/com.limpiadefensa.agent.plist"
    
    if File.exist?(source_plist)
      ohai "Deploying Limpia-Defensa LaunchAgent..."
      FileUtils.mkdir_p(File.dirname(agent_path))
      FileUtils.cp(source_plist, agent_path)
    end
  end

  def caveats
    <<~EOS
      ✊ Limpia-Defensa installed successfully!
      
      To start the secure REST API server background agent, run:
        launchctl load ~/Library/LaunchAgents/com.limpiadefensa.agent.plist
        
      The API server runs on port 8989. Verify running status:
        curl -i http://localhost:8989/?token=test-enterprise-token
        
      To use the CLI:
        limpia-defensa-cli --help
        
      To launch the native macOS GUI:
        limpia-defensa-gui
    EOS
  end

  test do
    system "#{bin}/limpia-defensa-cli", "--help"
  end
end
