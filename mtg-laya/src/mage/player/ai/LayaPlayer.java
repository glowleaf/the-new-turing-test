package mage.player.ai;

import mage.abilities.Ability;
import mage.cards.Card;
import mage.choices.Choice;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.*;

/**
 * LayaPlayer — the stock XMage greedy AI (ComputerPlayer8) with Laya
 * (convaiinnovations/laya on the DGX, default 192.168.1.166:5555) deciding the
 * choices that can be expressed as an enumerated, human-readable list.
 *
 * Intercepted decision points (v1):
 *   choose(Outcome, Choice, Game)      -> pick one of the enumerated options
 *   chooseUse(Outcome, String, ...)    -> YES / NO
 * Everything else falls through to ComputerPlayer8, so games stay legal and a
 * Laya player can be compared head-to-head against the same stock AI.
 *
 * Every Laya call is appended to laya_decisions.jsonl for measurement.
 */
public class LayaPlayer extends ComputerPlayer8 {

    public static String LAYA_URL = System.getProperty("laya.url", "http://192.168.1.166:5555");
    public static String LOG_PATH = System.getProperty("laya.log", "laya_decisions.jsonl");
    public static boolean ENABLED = Boolean.parseBoolean(System.getProperty("laya.enabled", "true"));
    /** more options than this go to the stock AI (Laya's choice space is small) */
    public static int MAX_OPTIONS = Integer.parseInt(System.getProperty("laya.maxOptions", "10"));

    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(4))
            .build();

    private final String pname;
    private static final Object LOG_LOCK = new Object();

    public LayaPlayer(String name, RangeOfInfluence range, int skill) {
        super(name, range, skill);
        this.pname = name;
    }

    // ------------------------------------------------------------------ logging
    private void log(String kind, String question, List<String> options, String answer,
                     double confidence, long ms, boolean used) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"player\":\"").append(esc(pname)).append("\",");
        sb.append("\"kind\":\"").append(esc(kind)).append("\",");
        sb.append("\"used\":").append(used).append(',');
        sb.append("\"question\":\"").append(esc(question)).append("\",");
        sb.append("\"options\":[");
        for (int i = 0; i < options.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append('"').append(esc(options.get(i))).append('"');
        }
        sb.append("],\"answer\":\"").append(esc(answer)).append("\",");
        sb.append("\"confidence\":").append(confidence).append(',');
        sb.append("\"ms\":").append(ms).append("}\n");
        synchronized (LOG_LOCK) {
            try {
                Files.writeString(Path.of(LOG_PATH), sb.toString(), StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (Exception ignore) { }
        }
    }

    private static String esc(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\\\"")
                .replace("\n", " ").replace("\r", " ");
    }

    /** strip XMage HTML markup + entities so Laya sees plain text; hard-cap length */
    private static String clean(String s) {
        if (s == null) return "";
        String t = s.replaceAll("<[^>]+>", " ")
                .replace("&mdash;", "-").replace("&nbsp;", " ")
                .replace("&amp;", "&").replace("&quot;", "\"")
                .replaceAll("\\s+", " ").trim();
        return t.length() > 120 ? t.substring(0, 120) : t;
    }

    // ------------------------------------------------------------------ state text
    private String boardState(Game game) {
        Player me = game.getPlayer(getId());
        Player opp = null;
        Set<UUID> opps = game.getOpponents(getId());
        if (opps != null && !opps.isEmpty()) {
            opp = game.getPlayer(opps.iterator().next());
        }
        StringBuilder sb = new StringBuilder(700);
        sb.append("turn ").append(game.getTurnNum())
          .append(", ").append(game.getTurnPhaseType())
          .append(' ').append(game.getTurnStepType())
          .append(". my life ").append(me == null ? "?" : me.getLife())
          .append(", opponent life ").append(opp == null ? "?" : opp.getLife()).append('.');
        sb.append(" my battlefield: ").append(describe(me, game));
        sb.append(" opponent battlefield: ").append(describe(opp, game));
        sb.append(" my hand: ").append(hand(me, game));
        if (me != null) {
            int handSize = opp == null ? 0 : opp.getHand().size();
            sb.append(" opponent hand size ").append(handSize).append('.');
        }
        return sb.toString();
    }

    private String describe(Player p, Game game) {
        if (p == null) return "(none)";
        StringBuilder sb = new StringBuilder();
        for (Permanent perm : game.getBattlefield().getAllActivePermanents(p.getId())) {
            if (perm == null) continue;
            if (sb.length() > 0) sb.append(", ");
            sb.append(perm.getName());
            if (perm.isCreature()) {
                sb.append(' ').append(perm.getPower().getValue())
                  .append('/').append(perm.getToughness().getValue());
                if (perm.isTapped()) sb.append(" tapped");
            } else if (perm.isLand()) {
                sb.append(perm.isTapped() ? " (land tapped)" : " (land)");
            }
        }
        return sb.length() == 0 ? "(empty)" : sb.toString();
    }

    private String hand(Player p, Game game) {
        if (p == null) return "(none)";
        StringBuilder sb = new StringBuilder();
        for (Card c : p.getHand().getCards(game)) {
            if (c == null) continue;
            if (sb.length() > 0) sb.append(", ");
            sb.append(c.getName());
        }
        return sb.length() == 0 ? "(empty)" : sb.toString();
    }

    // ------------------------------------------------------------------ Laya call
    /** returns the chosen option text, or null when Laya cannot answer */
    private String askLaya(String question, List<String> options, String state,
                           double[] confOut, long[] msOut) {
        if (!ENABLED) return null;
        try {
            StringBuilder body = new StringBuilder();
            body.append("{\"task\":\"decide\",\"text\":\"").append(esc(state)).append("\",");
            body.append("\"question\":\"").append(esc(question)).append("\",");
            body.append("\"choices\":[");
            for (int i = 0; i < options.size(); i++) {
                if (i > 0) body.append(',');
                body.append('"').append(esc(options.get(i))).append('"');
            }
            body.append("]}");

            long t0 = System.currentTimeMillis();
            HttpRequest req = HttpRequest.newBuilder(URI.create(LAYA_URL + "/decide"))
                    .timeout(Duration.ofSeconds(20))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString(), StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> resp = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            msOut[0] = System.currentTimeMillis() - t0;
            String choice = jsonField(resp.body(), "choice");
            String conf = jsonField(resp.body(), "confidence");
            confOut[0] = conf == null ? 0 : Double.parseDouble(conf);
            if (choice == null || choice.isEmpty() || choice.equals("UNCLEAR")) return null;
            return choice;
        } catch (Exception e) {
            msOut[0] = -1;
            return null;
        }
    }

    private static String jsonField(String json, String field) {
        if (json == null) return null;
        int i = json.indexOf("\"" + field + "\"");
        if (i < 0) return null;
        i = json.indexOf(':', i);
        if (i < 0) return null;
        i++;
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) i++;
        if (i >= json.length()) return null;
        char c = json.charAt(i);
        if (c == '"') {
            int j = json.indexOf('"', i + 1);
            return j < 0 ? null : json.substring(i + 1, j);
        }
        int j = i;
        while (j < json.length() && "-0123456789.eE".indexOf(json.charAt(j)) >= 0) j++;
        return json.substring(i, j);
    }

    // ------------------------------------------------------------------ overrides
    @Override
    public boolean choose(Outcome outcome, Choice choice, Game game) {
        try {
            Set<String> choices = choice.getChoices();
            if (choices != null && choices.size() >= 2 && choices.size() <= MAX_OPTIONS) {
                List<String> options = new ArrayList<>();
                for (String c : choices) options.add(clean(c));
                String question = clean(choice.getMessage());
                double[] conf = new double[]{0};
                long[] ms = new long[]{0};
                String picked = askLaya(
                        "Which option is best for me right now? " + (question == null ? "" : question),
                        options, boardState(game), conf, ms);
                boolean used = false;
                if (picked != null && options.contains(picked)) {
                    choice.setChoice(picked);
                    used = true;
                }
                log("choice", question, options, String.valueOf(picked), conf[0], ms[0], used);
                if (used) return true;
            }
        } catch (Exception ignore) {
            // fall through to the stock AI
        }
        return super.choose(outcome, choice, game);
    }

    @Override
    public boolean chooseUse(Outcome outcome, String message, Ability source, Game game) {
        try {
            List<String> options = Arrays.asList("YES do it", "NO do not");
            double[] conf = new double[]{0};
            long[] ms = new long[]{0};
            String picked = askLaya("Should I take this action?", options,
                    boardState(game) + " Proposed action: " + clean(message), conf, ms);
            boolean used = picked != null && options.contains(picked);
            log("chooseUse", clean(message), options, String.valueOf(picked), conf[0], ms[0], used);
            if (used) return picked.startsWith("YES");
        } catch (Exception ignore) { }
        return super.chooseUse(outcome, message, source, game);
    }

    @Override
    public boolean choose(Outcome outcome, mage.target.Target target, Ability source, Game game) {
        try {
            if (target.getTargets().isEmpty()) {
                java.util.Set<UUID> possible = target.possibleTargets(getId(), source, game);
                if (possible != null && possible.size() >= 2 && possible.size() <= MAX_OPTIONS) {
                    List<UUID> ids = new ArrayList<>(possible);
                    List<String> options = new ArrayList<>();
                    for (UUID id : ids) options.add(clean(nameOf(id, game)));
                    double[] conf = new double[]{0};
                    long[] ms = new long[]{0};
                    String picked = askLaya("Which target should I choose for " + abilityName(source) + "? "
                            + (target.getTargetName() == null ? "" : target.getTargetName()),
                            options, boardState(game), conf, ms);
                    boolean used = false;
                    if (picked != null) {
                        int idx = options.indexOf(picked);
                        if (idx >= 0) {
                            target.addTarget(ids.get(idx), source, game);
                            used = true;
                        }
                    }
                    log("target", "target for " + abilityName(source), options,
                            String.valueOf(picked), conf[0], ms[0], used);
                    if (used) return true;
                }
            }
        } catch (Exception ignore) { }
        return super.choose(outcome, target, source, game);
    }

    @Override
    public mage.abilities.TriggeredAbility chooseTriggeredAbility(
            List<mage.abilities.TriggeredAbility> abilities, Game game) {
        try {
            if (abilities != null && abilities.size() >= 2 && abilities.size() <= MAX_OPTIONS) {
                List<String> options = new ArrayList<>();
                for (mage.abilities.TriggeredAbility a : abilities) {
                    String t = a == null ? "?" : clean(a.toString());
                    options.add(t);
                }
                double[] conf = new double[]{0};
                long[] ms = new long[]{0};
                String picked = askLaya("Which triggered ability should I put on the stack first?",
                        options, boardState(game), conf, ms);
                boolean used = false;
                if (picked != null) {
                    int idx = options.indexOf(picked);
                    if (idx >= 0) {
                        log("trigger", "which trigger", options, picked, conf[0], ms[0], true);
                        return abilities.get(idx);
                    }
                }
                log("trigger", "which trigger", options, String.valueOf(picked), conf[0], ms[0], false);
            }
        } catch (Exception ignore) { }
        return super.chooseTriggeredAbility(abilities, game);
    }

    private static String abilityName(Ability a) {
        if (a == null) return "the current effect";
        try {
            String s = a.toString();
            return s.length() > 120 ? s.substring(0, 120) : s;
        } catch (Exception e) {
            return "the current effect";
        }
    }

    private static String nameOf(UUID id, Game game) {
        try {
            mage.MageObject o = game.getObject(id);
            if (o != null && o.getName() != null) return o.getName();
        } catch (Exception ignore) { }
        try {
            Player p = game.getPlayer(id);
            if (p != null) return p.getName();
        } catch (Exception ignore) { }
        return String.valueOf(id);
    }
}
