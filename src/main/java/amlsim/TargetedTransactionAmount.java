package amlsim;
import java.util.Random;

public class TargetedTransactionAmount {

   private SimProperties simProperties;
   private Random random;
   private double target;

   public TargetedTransactionAmount(Number target, Random random) {
       this.simProperties = AMLSim.getSimProp();
       this.random = random;
       this.target = target.doubleValue();
   }

    public double doubleValue() {
        double minTransactionAmount = simProperties.getMinTransactionAmount();
        double maxTransactionAmount = simProperties.getMaxTransactionAmount();
        double min, max, result;
        
        if (this.target < maxTransactionAmount) {
            max = this.target;
        } else {
            max = maxTransactionAmount;
        }
        
        if (this.target < minTransactionAmount) {
            min = this.target;
        } else {
            min = minTransactionAmount;
        }

        if (max - min <= 0) {
            result = this.target;
        } else {
            double modeSelector = random.nextDouble();

            if (modeSelector < 0.12) {
                double mu = 1.39;  // ln(4)
                double sigma = 1.3;
                result = Math.exp(mu + sigma * random.nextGaussian());
            } else if (modeSelector < 0.55) {
                double mu = 5.76;  // ln(316)
                double sigma = 1.0;
                result = Math.exp(mu + sigma * random.nextGaussian());
            } else {
                double mu = 8.06;  // ln(3162)
                double sigma = 1.2;
                result = Math.exp(mu + sigma * random.nextGaussian());
            }

            result = Math.max(min, Math.min(max, result));
        }
        return result;
    }
}