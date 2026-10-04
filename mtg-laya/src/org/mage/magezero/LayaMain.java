package org.mage.magezero;

import mage.cards.repository.CardScanner;
import mage.cards.repository.RepositoryUtil;
import mage.constants.RangeOfInfluence;
import mage.player.ai.LayaPlayer;
import mage.players.Player;

import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

/**
 * LayaMain — same harness as MageZeroMain, but it understands `type: laya`
 * in the player config and instantiates our LayaPlayer (stock greedy AI with
 * Laya deciding the enumerated choices).
 *
 * Run from the xmage/ directory:
 *   java -cp "lib/*;../classes" org.mage.magezero.LayaMain <abs path to config.yml>
 */
public class LayaMain extends ParallelDataGenerator {

    @Override
    protected Player createPlayer(String name, RangeOfInfluence rangeOfInfluence) {
        String type;
        if (name.equals("PlayerA")) {
            type = Config.INSTANCE.playerA.type;
        } else {
            type = Config.INSTANCE.playerB.type;
        }
        if ("laya".equals(type)) {
            System.out.println("[LAYA] creating LayaPlayer for " + name
                    + " url=" + System.getProperty("laya.url", "http://192.168.1.166:5555"));
            return new LayaPlayer(name, RangeOfInfluence.ONE, 6);
        }
        return super.createPlayer(name, rangeOfInfluence);
    }

    public static void main(String[] args) throws Exception {
        if (args.length > 0) {
            Config.load(args[0]);
        } else {
            Config.loadDefault();
        }
        System.out.println("[LAYA] playerA type=" + Config.INSTANCE.playerA.type
                + " deck=" + Config.INSTANCE.playerA.deckPath);
        System.out.println("[LAYA] playerB type=" + Config.INSTANCE.playerB.type
                + " deck=" + Config.INSTANCE.playerB.deckPath);

        Path lockPath = Paths.get("db", "magezero-bootstrap.lock");
        Files.createDirectories(lockPath.getParent());
        try (FileChannel channel = FileChannel.open(lockPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = channel.lock()) {
            RepositoryUtil.bootstrapLocalDb();
            CardScanner.scan();
        }

        new LayaMain().generateData();
        System.exit(0);
    }
}
